extends CharacterBody2D
class_name ServerBomb

# Server-authoritative bomb with progressive explosion system
# Supports both Power Glove throwing and kick abilities
# Uses Godot's built-in collision system with exceptions

const Constants = preload("res://shared/constants.gd")
const GridHelpers = preload("res://shared/game_logic/grid_helpers.gd")

# Bomb states for Power Glove system and kicking
enum BombState {
	PLANTED,    # Normal bomb on ground
	CARRIED,    # Being carried by player (Power Glove)
	THROWN,     # In mid-air flight (Power Glove)
	KICKED,     # Being kicked along ground
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
const THROW_DURATION: float = 0.3375  # Seconds per arc segment (fast throw)
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
var is_out_of_bounds: bool = false  # Track if bomb is currently outside map boundaries

# Bomb kick state
var kick_direction := Vector2.ZERO
var kick_speed := 200.0  # Speed when kicked (pixels per second)

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
signal kicked(bomb, direction)

func _ready():
	# Set collision layers: bombs on layer 3, collide with walls and players
	# Players need to collide with bombs to detect them for kicking/picking up
	collision_layer = Constants.COLLISION_LAYER_BOMBS
	collision_mask = Constants.COLLISION_LAYER_WALLS | Constants.COLLISION_LAYER_PLAYERS
	
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
			collision_mask = Constants.COLLISION_LAYER_WALLS | Constants.COLLISION_LAYER_PLAYERS
			state_changed.emit(self, bomb_state)
		return
	
	# Handle thrown state - update throw physics
	if bomb_state == BombState.THROWN:
		_update_throw_physics(delta)
		# Timer paused while thrown; restarts on landing. No mid-air explosion.
		return
	
	# Handle kicked bomb movement
	if bomb_state == BombState.KICKED:
		velocity = kick_direction * kick_speed
		var collision = move_and_collide(velocity * delta)
		
		if collision:
			# Stop the bomb when it hits something
			stop_kick()
			print("[Bomb] Kicked bomb stopped - hit ", collision.get_collider())
	
	# In planted/landed/kicked state (not carried/thrown/exploded), timer counts up
	if bomb_state == BombState.PLANTED or bomb_state == BombState.LANDED or bomb_state == BombState.KICKED:
		explosion_timer += delta
		if explosion_timer >= Constants.BOMB_TIMER:
			explode()

	if has_exploded:
		# Handle progressive explosion expansion
		if explosion_started and current_explosion_length <= explosion_range:
			explosion_growth_timer += delta
			if explosion_growth_timer >= EXPLOSION_GROWTH_INTERVAL:
				explosion_growth_timer -= EXPLOSION_GROWTH_INTERVAL
				expand_explosion()
		return

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
		"z_height": current_z_height,
		"is_visible": not is_out_of_bounds,
		"kick_direction": {"x": kick_direction.x, "y": kick_direction.y}
	}
	
	# Add throw-specific data if in THROWN state
	if bomb_state == BombState.THROWN:
		state_dict["throw_start"] = {"x": throw_start_pos.x, "y": throw_start_pos.y}
		state_dict["throw_target"] = {"x": throw_target_pos.x, "y": throw_target_pos.y}
		state_dict["throw_progress"] = throw_progress
		
		# Add current arc segment for smooth network interpolation
		state_dict["arc_start"] = {"x": current_arc_start.x, "y": current_arc_start.y}
		state_dict["arc_target"] = {"x": current_arc_target.x, "y": current_arc_target.y}
		state_dict["arc_height"] = current_arc_height
		state_dict["waypoint_index"] = current_waypoint_index
	
	return state_dict

# ============ POWER GLOVE SYSTEM METHODS ============

func can_be_picked_up() -> bool:
	"""Check if bomb can be picked up by a player with Power Glove"""
	# Cannot pick up if already carried, thrown, or kicked
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

# ============ END POWER GLOVE SYSTEM ============

# ============ BOMB KICK SYSTEM METHODS ============

func kick(direction: Vector2) -> bool:
	"""Kick the bomb in the given direction. Returns true if successful."""
	print("[Bomb] kick() called with direction: ", direction, " state=", bomb_state, " has_exploded=", has_exploded)
	
	# Cannot kick if already in motion or exploded
	if bomb_state != BombState.PLANTED or has_exploded:
		print("[Bomb] Cannot kick - wrong state or exploded")
		return false
	
	# Normalize direction to ensure consistent speed
	kick_direction = direction.normalized()
	bomb_state = BombState.KICKED
	
	# Clear any collision exceptions (player can no longer walk through this bomb)
	# Note: This requires iterating through all players, but we don't have a reference
	# The collision exceptions will naturally clear as the bomb moves away
	
	# Change collision layer to allow bomb to move through its original tile
	# Keep collision with walls and other bombs
	collision_layer = Constants.COLLISION_LAYER_BOMBS
	collision_mask = Constants.COLLISION_LAYER_WALLS | Constants.COLLISION_LAYER_BOMBS | Constants.COLLISION_LAYER_PLAYERS
	
	# Emit signals for network sync
	kicked.emit(self, kick_direction)
	state_changed.emit(self, bomb_state)
	
	print("[Bomb] Successfully kicked! Direction: ", kick_direction, " at speed ", kick_speed)
	return true

func stop_kick():
	"""Stop the bomb from sliding"""
	if bomb_state != BombState.KICKED:
		return
	
	bomb_state = BombState.PLANTED
	kick_direction = Vector2.ZERO
	velocity = Vector2.ZERO
	
	# Snap to grid center when stopped
	var tile_pos = get_tile_position()
	position = Vector2(
		tile_pos.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
		tile_pos.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
	)
	
	# Reset collision to normal
	collision_layer = Constants.COLLISION_LAYER_BOMBS
	collision_mask = Constants.COLLISION_LAYER_WALLS | Constants.COLLISION_LAYER_PLAYERS
	
	state_changed.emit(self, bomb_state)
	
	print("[Bomb] Stopped at tile ", tile_pos)

# ============ END BOMB KICK SYSTEM ============

# ============ THROW PHYSICS HELPER METHODS ============

func _calculate_bounce_waypoints(start_tile: Vector2i) -> Array[Vector2]:
	"""Calculate all bounce positions from throw start to final landing.
	
	Returns array of world positions for each bounce point (including final landing).
	Waypoints are calculated from the player's tile position (not bomb's offset position).
	Bounces on any collision (including out-of-bounds) and wraps around map edges.
	Adds intermediate waypoints at map boundaries for smooth visual transitions.
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
	var previous_tile: Vector2i = start_tile
	
	# Build waypoints by checking each potential landing spot
	var safety: int = 20
	while safety > 0:
		# Handle map wrap-around when going out of bounds
		var wrapped_tile = _wrap_tile_position(landing_tile)
		
		# Calculate tile center position (use wrapped coordinates)
		var tile_world_pos := Vector2(
			wrapped_tile.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
			wrapped_tile.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
		)
		
		# Check if tile is free or has collision
		var has_collision = _check_tile_has_collision(wrapped_tile)
		
		if has_collision:
			# Collision detected - check if continuing forward will cross boundary
			var next_tile = landing_tile + dir_i
			if _crosses_map_boundary(landing_tile, next_tile):
				# Don't add this tile as bounce - instead add edge transition waypoints
				_add_edge_transition_waypoints(waypoints, landing_tile, next_tile, dir_i)
				previous_tile = next_tile
				landing_tile = next_tile + dir_i
			else:
				# Normal bounce - add waypoint and continue
				waypoints.append(tile_world_pos)
				previous_tile = landing_tile
				landing_tile += dir_i
		else:
			# Found free tile - this is final landing
			waypoints.append(tile_world_pos)
			break
		
		safety -= 1
	
	if waypoints.size() == 0:
		# Fallback - calculate position relative to throw start
		var fallback_tile := start_tile + dir_i * 2
		var wrapped_fallback = _wrap_tile_position(fallback_tile)
		waypoints.append(Vector2(
			wrapped_fallback.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
			wrapped_fallback.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
		))
	
	return waypoints

func _wrap_tile_position(grid_pos: Vector2i) -> Vector2i:
	"""Wrap tile position around map edges (toroidal topology).
	
	If bomb goes off the right edge, it appears on the left.
	If bomb goes off the bottom, it appears on the top, etc.
	"""
	var wrapped_x = grid_pos.x
	var wrapped_y = grid_pos.y
	
	# Wrap X coordinate
	if wrapped_x < 0:
		wrapped_x = GameConfig.map_width + (wrapped_x % GameConfig.map_width)
	elif wrapped_x >= GameConfig.map_width:
		wrapped_x = wrapped_x % GameConfig.map_width
	
	# Wrap Y coordinate
	if wrapped_y < 0:
		wrapped_y = GameConfig.map_height + (wrapped_y % GameConfig.map_height)
	elif wrapped_y >= GameConfig.map_height:
		wrapped_y = wrapped_y % GameConfig.map_height
	
	return Vector2i(wrapped_x, wrapped_y)

func _crosses_map_boundary(from_tile: Vector2i, to_tile: Vector2i) -> bool:
	"""Check if movement from one tile to another crosses a map boundary."""
	# Check X boundary crossing
	if (from_tile.x >= 0 and from_tile.x < GameConfig.map_width) and \
	   (to_tile.x < 0 or to_tile.x >= GameConfig.map_width):
		return true
	
	# Check Y boundary crossing
	if (from_tile.y >= 0 and from_tile.y < GameConfig.map_height) and \
	   (to_tile.y < 0 or to_tile.y >= GameConfig.map_height):
		return true
	
	return false

func _add_edge_transition_waypoints(waypoints: Array[Vector2], from_tile: Vector2i, to_tile: Vector2i, direction: Vector2i):
	"""Add intermediate waypoints for smooth edge transitions.
	
	Adds only exit and entry waypoints - bomb will teleport between them.
	"""
	# Determine which edge is being crossed
	var exit_tile: Vector2i
	var entry_tile: Vector2i
	
	if to_tile.x < 0:
		# Crossing left edge -> wrapping to right
		exit_tile = Vector2i(0, from_tile.y)
		entry_tile = Vector2i(GameConfig.map_width - 1, from_tile.y)
	elif to_tile.x >= GameConfig.map_width:
		# Crossing right edge -> wrapping to left
		exit_tile = Vector2i(GameConfig.map_width - 1, from_tile.y)
		entry_tile = Vector2i(0, from_tile.y)
	elif to_tile.y < 0:
		# Crossing top edge -> wrapping to bottom
		exit_tile = Vector2i(from_tile.x, 0)
		entry_tile = Vector2i(from_tile.x, GameConfig.map_height - 1)
	elif to_tile.y >= GameConfig.map_height:
		# Crossing bottom edge -> wrapping to top
		exit_tile = Vector2i(from_tile.x, GameConfig.map_height - 1)
		entry_tile = Vector2i(from_tile.x, 0)
	else:
		return  # No boundary crossing
	
	# Add exit waypoint (last tile before leaving map)
	var exit_pos = Vector2(
		exit_tile.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
		exit_tile.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
	)
	waypoints.append(exit_pos)
	
	# Add entry waypoint (first tile after entering from opposite edge)
	# Bomb will teleport from exit to entry
	var entry_pos = Vector2(
		entry_tile.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
		entry_tile.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
	)
	waypoints.append(entry_pos)

func _check_tile_has_collision(grid_pos: Vector2i) -> bool:
	"""Check if a tile has any collision (wall, block, player, or bomb).
	
	Returns true if there's a collision (bomb should bounce).
	Returns false if tile is free (bomb can land).
	"""
	# Check static map (0 = empty, anything else = collision)
	if game_instance and game_instance.has_method("get_tile_type"):
		if game_instance.get_tile_type(grid_pos) != 0:
			return true  # Wall or destructible block
	
	# Check dynamic occupancy: players and other bombs
	if game_instance:
		# Players
		for peer_id in game_instance.players:
			var player = game_instance.players[peer_id]
			if is_instance_valid(player) and not player.is_dead:
				if player.get_tile_position() == grid_pos:
					return true  # Player collision - bounce
		# Bombs
		for other_id in game_instance.bombs:
			var other_bomb = game_instance.bombs[other_id]
			if is_instance_valid(other_bomb) and not other_bomb.has_exploded:
				if other_bomb.bomb_id != bomb_id and other_bomb.get_tile_position() == grid_pos:
					return true  # Bomb collision - bounce
	
	return false  # Tile is free

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
			
			# Check if this is a teleport segment (edge wrap)
			# If start and target are far apart but both in bounds, it's a teleport
			var distance = current_arc_start.distance_to(current_arc_target)
			var diagonal_distance = sqrt(
				pow(GameConfig.map_width * GameConfig.TILE_SIZE, 2) + 
				pow(GameConfig.map_height * GameConfig.TILE_SIZE, 2)
			)
			
			if distance > diagonal_distance * 0.5:
				# Large distance indicates edge wrap - teleport instantly
				throw_progress = 1.0
				return
			
			# Reset to standard arc height for bounces (no initial carry offset)
			current_arc_height = THROW_HEIGHT
			current_z_height = 0.0  # Bounces start from ground
	
	# Calculate current X/Y position along arc segment (ground-level trajectory)
	position = current_arc_start.lerp(current_arc_target, throw_progress)
	
	# Update visibility based on whether position is within map bounds
	# Check both tile position AND actual world position to handle interpolation
	var tile_pos = get_tile_position()
	var world_bounds_min = Vector2.ZERO
	var world_bounds_max = Vector2(
		GameConfig.map_width * GameConfig.TILE_SIZE,
		GameConfig.map_height * GameConfig.TILE_SIZE
	)
	
	# Out of bounds if tile is invalid OR position is outside world bounds
	is_out_of_bounds = not GridHelpers.is_valid_grid_position(tile_pos) or \
					   position.x < world_bounds_min.x or \
					   position.x >= world_bounds_max.x or \
					   position.y < world_bounds_min.y or \
					   position.y >= world_bounds_max.y
	
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
	
	# Reset Z height and ensure visible
	current_z_height = 0.0
	is_out_of_bounds = false
	
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

# ============ END THROW PHYSICS HELPER METHODS ============
