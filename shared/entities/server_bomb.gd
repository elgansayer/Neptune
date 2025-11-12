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
const THROW_RANGE: int = 3  # Grid tiles
const THROW_DURATION: float = 0.6  # Seconds for full throw
const THROW_HEIGHT: float = 100.0  # Peak Z-axis height in pixels
const THROW_BOUNCE_REDUCTION: float = 0.5  # Momentum reduction on bounce
var throw_start_pos: Vector2 = Vector2.ZERO
var throw_target_pos: Vector2 = Vector2.ZERO
var throw_direction: Vector2 = Vector2.ZERO
var throw_progress: float = 0.0  # 0.0 to 1.0
var throw_distance_remaining: int = THROW_RANGE
var current_z_height: float = 0.0  # Pseudo-3D height for shadow positioning

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
			# Position will be set by client-side visual attachment
			# Server just tracks the carrier
			explosion_timer -= delta  # Timer continues while carried
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
		explosion_timer -= delta  # Timer continues during throw
		
		# Check if timer expired mid-air
		if explosion_timer <= 0:
			explode()  # Bomb can explode in mid-air!
		return
	
	if has_exploded:
		# Handle progressive explosion expansion
		if explosion_started and current_explosion_length <= explosion_range:
			explosion_growth_timer += delta
			if explosion_growth_timer >= EXPLOSION_GROWTH_INTERVAL:
				explosion_growth_timer -= EXPLOSION_GROWTH_INTERVAL
				expand_explosion()
		return
	
	explosion_timer -= delta
	if explosion_timer <= 0:
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
	carrier_id = player.player_id if player.has("player_id") else ""
	
	# Disable collision while carried
	collision_layer = 0
	collision_mask = 0
	
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
	
	# Calculate throw trajectory
	bomb_state = BombState.THROWN
	throw_start_pos = carrying_player.position
	throw_direction = direction.normalized()
	throw_progress = 0.0
	throw_distance_remaining = THROW_RANGE
	
	# Calculate target position (server-authoritative)
	var final_tile = _calculate_throw_target()
	throw_target_pos = Vector2(
		final_tile.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
		final_tile.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
	)
	
	# Clear carrying references
	carrying_player = null
	carrier_id = ""
	
	# Emit signals for network sync
	thrown.emit(self, throw_start_pos, throw_target_pos, throw_direction)
	state_changed.emit(self, bomb_state)
	
	return true

func _calculate_throw_target() -> Vector2i:
	"""Calculate where the bomb will land (server-authoritative with collision)"""
	var start_tile = get_tile_position()
	var current_tile = start_tile
	var remaining_distance = THROW_RANGE
	
	# Cast forward to find landing position
	while remaining_distance > 0:
		var next_tile = current_tile + Vector2i(
			int(throw_direction.x),
			int(throw_direction.y)
		)
		
		# Check if next tile is valid and walkable
		var collision = check_tile_collision(next_tile)
		
		if collision["blocked"]:
			# Hit an obstacle - try to bounce to adjacent tile
			var bounce_tile = _find_bounce_tile(current_tile, next_tile)
			if bounce_tile != current_tile:
				# Successful bounce - reduce momentum and continue
				current_tile = bounce_tile
				remaining_distance = int(remaining_distance * THROW_BOUNCE_REDUCTION)
			else:
				# No valid bounce - land here
				break
		else:
			# Clear path - move to next tile
			current_tile = next_tile
			remaining_distance -= 1
	
	return current_tile

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
	"""Update bomb position during throw (called in _physics_process)"""
	if bomb_state != BombState.THROWN:
		return
	
	# Update throw progress
	throw_progress += delta / THROW_DURATION
	
	if throw_progress >= 1.0:
		# Throw complete - land the bomb
		_land_bomb()
		return
	
	# Calculate current position along arc
	position = throw_start_pos.lerp(throw_target_pos, throw_progress)
	
	# Calculate pseudo-3D height (parabolic arc)
	var height_progress = 1.0 - abs(throw_progress * 2.0 - 1.0)  # Peak at 0.5
	current_z_height = THROW_HEIGHT * height_progress

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
	
	# Transition to planted state
	bomb_state = BombState.PLANTED
	
	# Emit signals for network sync
	landed.emit(self, position)
	state_changed.emit(self, bomb_state)

# ============ END POWER GLOVE SYSTEM ============

func get_state() -> Dictionary:
	return {
		"bomb_id": bomb_id,
		"owner_id": owner_id,
		"position": {"x": position.x, "y": position.y},
		"timer": explosion_timer,
		"range": explosion_range
	}
