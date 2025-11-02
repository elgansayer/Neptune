extends CharacterBody2D
class_name ServerPlayer

# Server-authoritative player controller
# Uses Godot's built-in physics and collision system

const Constants = preload("res://shared/constants.gd")

var player_id: String = ""
var username: String = ""
var input_direction := Vector2.ZERO
var current_movement_direction := Vector2.ZERO  # Actual movement direction
var facing_direction := "DOWN"
var place_bomb_requested := false
var bombs_placed := 0
var max_bombs := 1
var bomb_range := 2
var is_dead := false

# Collision exceptions for bombs we've placed
var collision_exceptions := []

# Constants for automatic cornering
const TURN_ALIGNMENT_THRESHOLD = 20.0  # Distance from tile center to execute turn

func _ready():
	# Set up collision shape - USE CIRCLE for natural wall sliding!
	var collision_shape = CollisionShape2D.new()
	var shape = CircleShape2D.new()
	shape.radius = Constants.PLAYER_HALF_WIDTH  # 28 pixels radius (56px diameter, 87.5% of 64px tile)
	collision_shape.shape = shape
	add_child(collision_shape)

func _physics_process(_delta):
	if is_dead:
		velocity = Vector2.ZERO
		current_movement_direction = Vector2.ZERO
		move_and_slide()
		return
	
	# Get strict 4-way input
	var input_dir = get_4way_input()
	
	# Debug current state
	if input_dir.length() > 0 or current_movement_direction.length() > 0:
		print("[%s] Input: %s, CurrentMove: %s" % [player_id, input_dir, current_movement_direction])
	
	# Simple input buffering: last input wins
	if input_dir.length() > Constants.INPUT_DEADZONE:
		# There's input - move in that direction
		if input_dir != current_movement_direction:
			print("[%s] Moving in new direction: %s" % [player_id, input_dir])
		current_movement_direction = input_dir
	else:
		# No input - stop
		if current_movement_direction.length() > 0:
			print("[%s] STOP" % player_id)
		current_movement_direction = Vector2.ZERO
	
	# Apply movement
	if current_movement_direction.length() > 0:
		var speed = Constants.BASE_SPEED * Constants.RUN_MULTIPLIER
		velocity = current_movement_direction * speed
		
		# Update facing
		if abs(current_movement_direction.y) > abs(current_movement_direction.x):
			facing_direction = "UP" if current_movement_direction.y < 0 else "DOWN"
		else:
			facing_direction = "LEFT" if current_movement_direction.x < 0 else "RIGHT"
	else:
		velocity = Vector2.ZERO
	
	move_and_slide()
	
	# Clear collision exceptions when player is no longer overlapping bomb
	for i in range(collision_exceptions.size() - 1, -1, -1):
		var bomb = collision_exceptions[i]
		if not is_instance_valid(bomb):
			collision_exceptions.remove_at(i)
			continue
		
		var player_tile = get_tile_position()
		var bomb_tile = bomb.get_tile_position()
		
		if player_tile != bomb_tile:
			bomb.remove_collision_exception_with(self)
			collision_exceptions.remove_at(i)

func get_4way_input() -> Vector2:
	"""Convert input to strict 4-way cardinal directions (no diagonal movement)"""
	if input_direction.length() < Constants.INPUT_DEADZONE:
		return Vector2.ZERO
	
	# Choose the stronger axis
	if abs(input_direction.x) > abs(input_direction.y):
		# Horizontal movement
		return Vector2(sign(input_direction.x), 0.0)
	else:
		# Vertical movement
		return Vector2(0.0, sign(input_direction.y))

func get_current_tile_center() -> Vector2:
	"""Get the center position of the tile the player is currently on"""
	var tile_x = floor(position.x / Constants.TILE_SIZE)
	var tile_y = floor(position.y / Constants.TILE_SIZE)
	return Vector2(
		tile_x * Constants.TILE_SIZE + Constants.TILE_SIZE / 2.0,
		tile_y * Constants.TILE_SIZE + Constants.TILE_SIZE / 2.0
	)

func is_perpendicular(dir1: Vector2, dir2: Vector2) -> bool:
	"""Check if two direction vectors are perpendicular (90 degrees apart)"""
	if dir1.length() < 0.1 or dir2.length() < 0.1:
		return false
	# Dot product is 0 for perpendicular vectors
	return abs(dir1.dot(dir2)) < 0.1

func is_opposite(dir1: Vector2, dir2: Vector2) -> bool:
	"""Check if two direction vectors are opposite (180 degrees apart)"""
	if dir1.length() < 0.1 or dir2.length() < 0.1:
		return false
	# Dot product is -1 for opposite vectors
	return dir1.dot(dir2) < -0.9

func is_tile_walkable(tile_pos: Vector2i) -> bool:
	"""Check if a tile position is walkable (not a wall or block)"""
	var game_instance = get_parent()
	if not game_instance or not game_instance.has_method("get"):
		return true  # Assume walkable if we can't check
	
	var game_map = game_instance.game_map
	if not game_map:
		return true
	
	# Check bounds
	if tile_pos.y < 0 or tile_pos.y >= game_map.size():
		return false
	if tile_pos.x < 0 or tile_pos.x >= game_map[0].size():
		return false
	
	# Check tile type: 0 = empty (walkable), 1 = wall, 2 = destructible block
	var tile_type = game_map[tile_pos.y][tile_pos.x]
	return tile_type == 0

func get_tile_position() -> Vector2i:
	return Vector2i(
		int(floor(position.x / Constants.TILE_SIZE)),
		int(floor(position.y / Constants.TILE_SIZE))
	)

func set_input(input_x: float, input_y: float):
	input_direction = Vector2(input_x, input_y)

func request_bomb_placement():
	place_bomb_requested = true

func can_place_bomb() -> bool:
	return bombs_placed < max_bombs and not place_bomb_requested

func add_bomb_collision_exception(bomb):
	if bomb not in collision_exceptions:
		collision_exceptions.append(bomb)
		bomb.add_collision_exception_with(self)

func die():
	is_dead = true
	# TODO: Play death animation
	# TODO: Respawn logic

func get_state() -> Dictionary:
	return {
		"player_id": player_id,
		"username": username,
		"position": {"x": position.x, "y": position.y},
		"velocity": {"x": velocity.x, "y": velocity.y},
		"facing": facing_direction,
		"is_dead": is_dead,
		"bombs_placed": bombs_placed,
		"max_bombs": max_bombs,
		"bomb_range": bomb_range
	}
