extends CharacterBody2D
class_name ServerBomb

# Server-authoritative bomb with progressive explosion system
# Supports being kicked by players with the kick ability
# Uses Godot's built-in collision system with exceptions

const Constants = preload("res://shared/constants.gd")
const GridHelpers = preload("res://shared/game_logic/grid_helpers.gd")

var bomb_id: String = ""
var owner_id: String = ""
var explosion_range: int = 2
var explosion_timer: float = Constants.BOMB_TIMER
var has_exploded := false
var game_instance: Node = null  # Reference to GameInstance for collision checking

# Bomb kick state
var is_kicked := false
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
	if has_exploded:
		# Handle progressive explosion expansion
		if explosion_started and current_explosion_length <= explosion_range:
			explosion_growth_timer += delta
			if explosion_growth_timer >= EXPLOSION_GROWTH_INTERVAL:
				explosion_growth_timer -= EXPLOSION_GROWTH_INTERVAL
				expand_explosion()
		return
	
	# Handle kicked bomb movement
	if is_kicked:
		velocity = kick_direction * kick_speed
		var collision = move_and_collide(velocity * delta)
		
		if collision:
			# Stop the bomb when it hits something
			stop_kick()
			print("[Bomb] Kicked bomb stopped - hit ", collision.get_collider())
	
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
	return {
		"bomb_id": bomb_id,
		"owner_id": owner_id,
		"position": {"x": position.x, "y": position.y},
		"timer": explosion_timer,
		"range": explosion_range,
		"is_kicked": is_kicked,
		"kick_direction": {"x": kick_direction.x, "y": kick_direction.y}
	}

func kick(direction: Vector2):
	"""Kick the bomb in the given direction"""
	print("[Bomb] kick() called with direction: ", direction, " is_kicked=", is_kicked, " has_exploded=", has_exploded)
	
	if is_kicked or has_exploded:
		print("[Bomb] Already kicked or exploded, ignoring kick")
		return
	
	# Normalize direction to ensure consistent speed
	kick_direction = direction.normalized()
	is_kicked = true
	
	# Clear any collision exceptions (player can no longer walk through this bomb)
	# Note: This requires iterating through all players, but we don't have a reference
	# The collision exceptions will naturally clear as the bomb moves away
	
	# Change collision layer to allow bomb to move through its original tile
	# Keep collision with walls and other bombs
	collision_layer = Constants.COLLISION_LAYER_BOMBS
	collision_mask = Constants.COLLISION_LAYER_WALLS | Constants.COLLISION_LAYER_BOMBS | Constants.COLLISION_LAYER_PLAYERS
	
	print("[Bomb] Successfully kicked! Direction: ", kick_direction, " at speed ", kick_speed)

func stop_kick():
	"""Stop the bomb from sliding"""
	if not is_kicked:
		return
	
	is_kicked = false
	kick_direction = Vector2.ZERO
	velocity = Vector2.ZERO
	
	# Snap to grid center when stopped
	var tile_pos = get_tile_position()
	position = Vector2(
		tile_pos.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
		tile_pos.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
	)
	
	print("[Bomb] Stopped at tile ", tile_pos)
