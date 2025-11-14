extends StaticBody2D
class_name ServerBomb

# Server-authoritative bomb with progressive explosion system and Power Glove throwing
# Uses Godot's built-in collision system with exceptions

const Constants = preload("res://shared/constants.gd")
const GridHelpers = preload("res://shared/game_logic/grid_helpers.gd")

# Bomb states for Power Glove system
enum BombState {
	PLANTED,    # Normal bomb on ground
	CARRIED,    # Being carried by player
	THROWN,     # In mid-air flight
	LANDED      # Just landed after throw
}

var bomb_id: String = ""
var owner_id: String = ""
var explosion_range: int = 2
var explosion_timer: float = Constants.BOMB_TIMER
var has_exploded := false
var game_instance: Node = null  # Reference to GameInstance for collision checking

# Power Glove throwing state
var bomb_state: BombState = BombState.PLANTED
var carrying_player: Node = null  # Reference to player carrying this bomb
var carrier_id: String = ""

# Throw physics (pseudo-3D arc simulation)
const THROW_RANGE: int = 2  # Grid tiles
const THROW_DURATION: float = 0.375  # Seconds per arc segment (fast throw)
const THROW_HEIGHT: float = 8.0  # Visual height in pixels for arc
const BOUNCE_HEIGHT_REDUCTION: float = 0.6  # Height reduction per bounce
var throw_start_pos: Vector2 = Vector2.ZERO
var throw_target_pos: Vector2 = Vector2.ZERO
var throw_direction: Vector2 = Vector2.ZERO
var throw_progress: float = 0.0  # 0.0 to 1.0 within current segment
var throw_distance_remaining: int = THROW_RANGE
var current_z_height: float = 0.0  # Pseudo-3D height for shadow positioning
var bounce_waypoints: Array[Vector2] = []  # List of bounce positions
var current_waypoint_index: int = 0
var current_arc_start: Vector2 = Vector2.ZERO
var current_arc_target: Vector2 = Vector2.ZERO
var current_arc_height: float = THROW_HEIGHT

# Progressive explosion state
const EXPLOSION_GROWTH_INTERVAL = 0.02  # 50 tiles/second
var explosion_started := false
var explosion_growth_timer := 0.0
var current_explosion_length := 1
var explosion_pattern: Array[Dictionary] = []  # Full explosion pattern calculated at start

# Direction data for explosion expansion (up, down, left, right)
var explosion_directions := [
	{"name": "up", "offset": Vector2i(0, -1), "max_length": 0},
	{"name": "down", "offset": Vector2i(0, 1), "max_length": 0},
	{"name": "left", "offset": Vector2i(-1, 0), "max_length": 0},
	{"name": "right", "offset": Vector2i(1, 0), "max_length": 0}
]

signal exploded(bomb, explosion_pattern)
signal explosion_expanded(tiles)
signal state_changed(bomb, new_state)
signal picked_up(bomb, player)
signal thrown(bomb, start_pos, target_pos, direction)
signal landed(bomb, final_pos)

func _ready():
	# Set collision layers: bombs on layer 3, collide with walls (1) only
	collision_layer = Constants.COLLISION_LAYER_BOMBS
	collision_mask = Constants.COLLISION_LAYER_WALLS
	
	# Set up collision shape
	var collision_shape = CollisionShape2D.new()
	var shape = RectangleShape2D.new()
	shape.size = Vector2(GameConfig.TILE_SIZE * 0.7, GameConfig.TILE_SIZE * 0.7)  # Slightly smaller than tile
	collision_shape.shape = shape
	add_child(collision_shape)
	
	# Center on tile
	var tile_pos = get_tile_position()
	position = Vector2(
		tile_pos.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
		tile_pos.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
	)

func _physics_process(delta):
	# Handle carried state - follow player position
	if bomb_state == BombState.CARRIED:
		if is_instance_valid(carrying_player):
			# Attach to carrier with animated offset based on pickup animation
			var bomb_offset = carrying_player.get_carried_bomb_offset()
			position = carrying_player.position + bomb_offset
			current_z_height = 0.0  # visual z handled client-side if needed
			# Timer paused while carried
		else:
			# Carrier invalid - drop bomb
			bomb_state = BombState.PLANTED
			collision_layer = Constants.COLLISION_LAYER_BOMBS
			collision_mask = Constants.COLLISION_LAYER_WALLS
			state_changed.emit(self, bomb_state)
		return
	
	# Handle thrown state - update throw physics
	if bomb_state == BombState.THROWN:
		_update_throw_physics(delta)
		# Timer paused while thrown; restarts on landing. No mid-air explosion.
		return
	
	if has_exploded:
		# Handle progressive explosion expansion
		if explosion_started and current_explosion_length <= explosion_range:
			explosion_growth_timer += delta
			if explosion_growth_timer >= EXPLOSION_GROWTH_INTERVAL:
				explosion_growth_timer -= EXPLOSION_GROWTH_INTERVAL
				expand_explosion()
		return
	
	# In planted/landed state (not carried/thrown/exploded), timer counts up
	explosion_timer += delta
	if explosion_timer >= Constants.BOMB_TIMER:
		explode()

func get_tile_position() -> Vector2i:
	return Vector2i(
		int(floor(position.x / GameConfig.TILE_SIZE)),
		int(floor(position.y / GameConfig.TILE_SIZE))
	)

func explode():
	if has_exploded:
		return
	
	has_exploded = true
	explosion_started = true
	
	# If exploding mid-air (THROWN state), use shadow position on grid
	# The hitbox applies to the bomb's X/Y position on the ground, not the visual Z height
	# (Already handled by get_tile_position() which uses 2D position)
	
	# Calculate full explosion pattern at start (for network efficiency)
	calculate_explosion_pattern()
	
	# Emit explosion with pattern for network sync
	exploded.emit(self, explosion_pattern)
	
	# Start progressive expansion
	current_explosion_length = 0
	explosion_growth_timer = 0.0

func calculate_explosion_pattern():
	"""Calculate the full explosion pattern before starting expansion"""
	var tile_pos = get_tile_position()
	explosion_pattern.clear()
	
	# Add center tile
	explosion_pattern.append({
		"grid_pos": {"x": tile_pos.x, "y": tile_pos.y},
		"direction": "middle",
		"length": 0,
		"is_end": false
	})
	
	# Calculate max length for each direction by raycasting
	for dir_data in explosion_directions:
		var offset = dir_data["offset"]
		var max_length = explosion_range
		
		# Raycast to find obstacles
		for i in range(1, explosion_range + 1):
			var check_pos = tile_pos + offset * i
			var collision_result = check_tile_collision(check_pos)
			
			if collision_result["blocked"]:
				max_length = i if collision_result["destructible"] else i - 1
				break
		
		dir_data["max_length"] = max_length
		
		# Add all tiles in this direction to pattern
		for i in range(1, max_length + 1):
			var grid_pos = tile_pos + offset * i
			explosion_pattern.append({
				"grid_pos": {"x": grid_pos.x, "y": grid_pos.y},
				"direction": dir_data["name"],
				"length": i,
				"is_end": i == max_length
			})

func check_tile_collision(grid_pos: Vector2i) -> Dictionary:
	"""Check if a tile position has a collision (wall or destructible block)"""
	# Bounds check
	if not GridHelpers.is_valid_grid_position(grid_pos):
		return {"blocked": true, "destructible": false}
	
	# Check game map if game_instance is available
	if game_instance and game_instance.has_method("get_tile_type"):
		var tile_type = game_instance.get_tile_type(grid_pos)
		if tile_type == 1:  # Solid wall
			return {"blocked": true, "destructible": false}
		elif tile_type == 2:  # Destructible block
			return {"blocked": true, "destructible": true}
	
	return {"blocked": false, "destructible": false}

func expand_explosion():
	"""Expand explosion by one tile in all directions"""
	current_explosion_length += 1
	
	if current_explosion_length > explosion_range:
		# Explosion complete, remove bomb after short delay
		await get_tree().create_timer(0.5).timeout
		queue_free()
		return
	
	# Get tiles at current expansion length for collision detection
	var tile_pos = get_tile_position()
	var tiles_this_frame: Array[Vector2i] = []
	
	for dir_data in explosion_directions:
		if current_explosion_length <= dir_data["max_length"]:
			var offset = dir_data["offset"]
			var fire_pos = tile_pos + offset * current_explosion_length
			tiles_this_frame.append(fire_pos)
	
	# Emit signal for GameInstance to handle damage/destruction
	# (Will be connected by GameInstance)
	if has_signal("explosion_expanded"):
		emit_signal("explosion_expanded", tiles_this_frame)

func get_state() -> Dictionary:
	var state_dict = {
		"bomb_id": bomb_id,
		"owner_id": owner_id,
		"position": {"x": position.x, "y": position.y},
		"timer": explosion_timer,
		"range": explosion_range,
		"state": bomb_state,
		"carrier_id": carrier_id,
		"z_height": current_z_height
	}
	
	# Add throw-specific data if in THROWN state
	if bomb_state == BombState.THROWN:
		state_dict["throw_start"] = {"x": throw_start_pos.x, "y": throw_start_pos.y}
		state_dict["throw_target"] = {"x": throw_target_pos.x, "y": throw_target_pos.y}
		state_dict["throw_progress"] = throw_progress
	
	return state_dict

# ============ POWER GLOVE SYSTEM METHODS ============

func can_be_picked_up() -> bool:
	"""Check if bomb can be picked up by a player with Power Glove"""
	# Cannot pick up if already carried or thrown
	if bomb_state != BombState.PLANTED:
		return false
	
	# Cannot pick up if already exploding
	if has_exploded or explosion_started:
		return false
	
	return true

func pick_up(player: Node) -> bool:
	"""Pick up the bomb (called by server when player with Power Glove presses action)"""
	if not can_be_picked_up():
		return false
	
	# Change state to carried
	bomb_state = BombState.CARRIED
	carrying_player = player
	# ServerPlayer defines `player_id`; avoid using non-existent Object.has()
	carrier_id = player.player_id
	
	# Disable collision while carried
	collision_layer = 0
	collision_mask = 0

	# Immediately sync position to carrier for authoritative state
	position = player.position
	
	# Emit signals for network sync
	picked_up.emit(self, player)
	state_changed.emit(self, bomb_state)
	
	return true

func throw_bomb(direction: Vector2) -> bool:
	"""Throw the bomb in a direction (called by server when carrier releases action)"""
	if bomb_state != BombState.CARRIED:
		return false
	
	if not is_instance_valid(carrying_player):
		return false
	
	# Calculate throw trajectory with bounce waypoints
	bomb_state = BombState.THROWN
	# Store the actual start position (includes overhead offset) for network sync
	throw_start_pos = position
	throw_direction = direction.normalized()
	throw_progress = 0.0
	throw_distance_remaining = THROW_RANGE
	
	# Get player's tile as the throw origin (not bomb's current tile which may be offset)
	var player_tile = carrying_player.get_tile_position()
	
	# Calculate all bounce waypoints (server-authoritative)
	bounce_waypoints = _calculate_bounce_waypoints(player_tile)
	
	# Final target is last waypoint
	if bounce_waypoints.size() > 0:
		throw_target_pos = bounce_waypoints[-1]
	else:
		# Fallback
		throw_target_pos = throw_start_pos + throw_direction * GameConfig.TILE_SIZE * 2
	
	# Initialize arc segment tracking
	current_waypoint_index = 0
	# For physics, always use ground-level positions (tile centers)
	# Use player's tile position as throw origin (not bomb's offset position)
	var start_tile_center = Vector2(
		player_tile.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
		player_tile.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
	)
	current_arc_start = start_tile_center
	if bounce_waypoints.size() > 0:
		current_arc_target = bounce_waypoints[0]
	else:
		current_arc_target = throw_target_pos
	
	# Calculate initial z_height to match where bomb is currently held
	# This creates smooth transition from carried position to arc
	var carry_offset = throw_start_pos - start_tile_center
	current_z_height = -carry_offset.y  # Convert Y offset to z_height
	current_arc_height = THROW_HEIGHT
	print("[ServerBomb] throw_bomb() - Starting z_height: ", current_z_height, ", arc height: ", current_arc_height)
	
	# Clear carrying references
	carrying_player = null
	carrier_id = ""
	
	# Emit signals for network sync
	thrown.emit(self, throw_start_pos, throw_target_pos, throw_direction)
	state_changed.emit(self, bomb_state)
	
	return true

func _calculate_bounce_waypoints(start_tile: Vector2i) -> Array[Vector2]:
	"""Calculate all bounce positions from throw start to final landing.
	
	Returns array of world positions for each bounce point (including final landing).
	Waypoints are calculated from the player's tile position (not bomb's offset position).
	"""
	# Cardinalize throw direction
	var dir_i: Vector2i = Vector2i(0, 0)
	if abs(throw_direction.x) > abs(throw_direction.y):
		dir_i.x = int(sign(throw_direction.x))
	else:
		dir_i.y = int(sign(throw_direction.y))
	if dir_i == Vector2i.ZERO:
		dir_i = Vector2i(0, 1)
	
	var waypoints: Array[Vector2] = []
	var landing_tile: Vector2i = start_tile + dir_i * 2
	
	# Build waypoints by checking each potential landing spot
	var safety: int = 20
	while safety > 0:
		if not GridHelpers.is_valid_grid_position(landing_tile):
			# Out of bounds - step back
			landing_tile -= dir_i
			break
		
		# Calculate tile center position
		var tile_world_pos := Vector2(
			landing_tile.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
			landing_tile.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
		)
		
		if _is_tile_free_for_landing(landing_tile):
			# Found free tile - this is final landing
			waypoints.append(tile_world_pos)
			break
		else:
			# Blocked - add as bounce waypoint and continue
			waypoints.append(tile_world_pos)
			landing_tile += dir_i
		
		safety -= 1
	
	if waypoints.size() == 0:
		# Fallback - calculate position relative to throw start
		var fallback_tile := start_tile + dir_i * 2
		waypoints.append(Vector2(
			fallback_tile.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
			fallback_tile.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
		))
	
	return waypoints

func _calculate_throw_target() -> Vector2i:
	"""Calculate where the bomb will land (server-authoritative, fixed 2-tile throw).

	Rules:
	- ALWAYS throw exactly +2 tiles in the cardinal direction (ignoring blockers).
	- When landing, if the tile is not empty, bounce +1 tile forward.
	- Continue bouncing +1 until finding an empty tile or hitting map bounds.
	"""
	var start_tile: Vector2i = get_tile_position()

	# Cardinalize throw direction to strict grid steps
	var dir_i: Vector2i = Vector2i(0, 0)
	if abs(throw_direction.x) > abs(throw_direction.y):
		dir_i.x = int(sign(throw_direction.x))
	else:
		dir_i.y = int(sign(throw_direction.y))
	if dir_i == Vector2i.ZERO:
		# Fallback - default DOWN
		dir_i = Vector2i(0, 1)

	# Always target +2 tiles initially
	var landing_tile: Vector2i = start_tile + dir_i * 2
	
	# Bounce forward +1 at a time until we find an empty tile
	var safety: int = 20  # Prevent infinite loops
	while safety > 0:
		# Check if current landing tile is valid and free
		if not GridHelpers.is_valid_grid_position(landing_tile):
			# Out of bounds - use last valid tile we calculated
			landing_tile -= dir_i
			break
		
		if _is_tile_free_for_landing(landing_tile):
			# Found a free tile, land here
			return landing_tile
		
		# Tile is blocked, bounce +1 forward
		landing_tile += dir_i
		safety -= 1
	
	# Fallback: if we exhausted safety or went OOB, return best guess
	if GridHelpers.is_valid_grid_position(landing_tile):
		return landing_tile
	return start_tile

func _is_tile_free_for_landing(grid_pos: Vector2i) -> bool:
	"""Check if a tile is suitable for landing: empty map cell and no players/bombs.
	Ignores this bomb's own ID when checking bombs.
	"""
	# Must be in bounds
	if not GridHelpers.is_valid_grid_position(grid_pos):
		return false

	# Check static map first (0 = empty)
	if game_instance and game_instance.has_method("get_tile_type"):
		if game_instance.get_tile_type(grid_pos) != 0:
			return false
	
	# Check dynamic occupancy: players and other bombs
	if game_instance:
		# Players
		for peer_id in game_instance.players:
			var player = game_instance.players[peer_id]
			if is_instance_valid(player) and not player.is_dead:
				if player.get_tile_position() == grid_pos:
					return false
		# Bombs
		for other_id in game_instance.bombs:
			var other_bomb = game_instance.bombs[other_id]
			if is_instance_valid(other_bomb) and not other_bomb.has_exploded:
				if other_bomb.bomb_id != bomb_id and other_bomb.get_tile_position() == grid_pos:
					return false

	return true

func _find_bounce_tile(current_tile: Vector2i, blocked_tile: Vector2i) -> Vector2i:
	"""Find an adjacent tile to bounce to when landing is blocked"""
	# Try perpendicular directions
	var perpendiculars = []
	
	if throw_direction.x != 0:
		# Throwing horizontally, try up/down
		perpendiculars.append(Vector2i(0, -1))
		perpendiculars.append(Vector2i(0, 1))
	else:
		# Throwing vertically, try left/right
		perpendiculars.append(Vector2i(-1, 0))
		perpendiculars.append(Vector2i(1, 0))
	
	# Check each perpendicular direction
	for perp_dir in perpendiculars:
		var bounce_tile = current_tile + perp_dir
		var collision = check_tile_collision(bounce_tile)
		
		if not collision["blocked"]:
			return bounce_tile
	
	# Try continuing forward with reduced momentum (slide along wall)
	var forward_tile = blocked_tile + Vector2i(
		int(throw_direction.x),
		int(throw_direction.y)
	)
	var forward_collision = check_tile_collision(forward_tile)
	if not forward_collision["blocked"]:
		return forward_tile
	
	# No valid bounce - stay at current tile
	return current_tile

func _update_throw_physics(delta: float):
	"""Update bomb position during throw with bounces (called in _physics_process)"""
	if bomb_state != BombState.THROWN:
		return
	
	# Update progress within current arc segment
	throw_progress += delta / THROW_DURATION
	
	if throw_progress >= 1.0:
		# Completed current arc segment
		current_waypoint_index += 1
		
		if current_waypoint_index >= bounce_waypoints.size():
			# All segments complete - land the bomb
			_land_bomb()
			return
		else:
			# Move to next arc segment (bounce) - start from ground level
			throw_progress = 0.0
			current_arc_start = current_arc_target
			current_arc_target = bounce_waypoints[current_waypoint_index]
			# Reset to standard arc height for bounces (no initial carry offset)
			current_arc_height = THROW_HEIGHT
			current_z_height = 0.0  # Bounces start from ground
	
	# Calculate current X/Y position along arc segment (ground-level trajectory)
	position = current_arc_start.lerp(current_arc_target, throw_progress)
	
	# Calculate pseudo-3D height (parabolic arc)
	# For first segment (index 0), we need to transition from initial carry z_height
	if current_waypoint_index == 0:
		# Blend from initial z_height (carry offset) to parabolic arc
		var initial_z = -((throw_start_pos - current_arc_start).y)  # Initial height from carry
		var peak_z = current_arc_height
		
		# Create arc that starts at initial_z, peaks at peak_z, and ends at 0
		# Use a quadratic bezier-like curve
		var t = throw_progress
		var arc_z = initial_z * (1.0 - t) * (1.0 - t) + peak_z * 2.0 * t * (1.0 - t) + 0.0 * t * t
		current_z_height = arc_z
	else:
		# Standard parabolic arc for bounces (starts and ends at ground)
		var height_progress = 1.0 - abs(throw_progress * 2.0 - 1.0)  # Peak at 0.5
		current_z_height = current_arc_height * height_progress

func _land_bomb():
	"""Land the bomb at final position and snap to grid"""
	bomb_state = BombState.LANDED
	
	# Snap to grid center
	var final_tile = get_tile_position()
	position = Vector2(
		final_tile.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
		final_tile.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
	)
	
	# Reset Z height
	current_z_height = 0.0
	
	# Re-enable collision
	collision_layer = Constants.COLLISION_LAYER_BOMBS
	collision_mask = Constants.COLLISION_LAYER_WALLS

	# Restart fuse from zero upon landing
	explosion_timer = 0.0
	
	# Transition to planted state
	bomb_state = BombState.PLANTED
	
	# Emit signals for network sync
	landed.emit(self, position)
	state_changed.emit(self, bomb_state)

# ============ END POWER GLOVE SYSTEM ============
