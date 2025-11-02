extends CharacterBody2D
class_name ServerPlayer

# Server-authoritative player controller
# Uses Godot's built-in physics and collision system

const Constants = preload("res://shared/constants.gd")

var player_id: String = ""
var username: String = ""
var input_direction := Vector2.ZERO
var facing_direction := "DOWN"
var place_bomb_requested := false
var bombs_placed := 0
var max_bombs := 1
var bomb_range := 2
var is_dead := false

# Collision exceptions for bombs we've placed
var collision_exceptions := []

func _ready():
	# Set up collision shape
	var collision_shape = CollisionShape2D.new()
	var shape = RectangleShape2D.new()
	shape.size = Vector2(Constants.PLAYER_HALF_WIDTH * 2, Constants.PLAYER_HALF_WIDTH * 2)
	collision_shape.shape = shape
	add_child(collision_shape)

func _physics_process(_delta):
	if is_dead:
		velocity = Vector2.ZERO
		move_and_slide()
		return
	
	# Get strict 4-way input
	var move_dir = get_4way_input()
	
	# Calculate movement velocity - pure cardinal movement, no nudging
	if move_dir.length() > Constants.INPUT_DEADZONE:
		# Moving - apply speed in the input direction
		var speed = Constants.BASE_SPEED * Constants.RUN_MULTIPLIER
		velocity = move_dir * speed
		
		# Update facing direction
		if abs(move_dir.y) > abs(move_dir.x):
			facing_direction = "UP" if move_dir.y < 0 else "DOWN"
		else:
			facing_direction = "LEFT" if move_dir.x < 0 else "RIGHT"
	else:
		# Stopped - player stays exactly where they are
		velocity = Vector2.ZERO
	
	# Move with Godot's physics - natural wall sliding when off-center
	move_and_slide()
	
	# Clear collision exceptions when player is no longer overlapping bomb
	for i in range(collision_exceptions.size() - 1, -1, -1):
		var bomb = collision_exceptions[i]
		if not is_instance_valid(bomb):
			collision_exceptions.remove_at(i)
			continue
		
		# Check if we're on a different tile AND not overlapping
		var player_tile = get_tile_position()
		var bomb_tile = bomb.get_tile_position()
		
		if player_tile != bomb_tile:
			# Clear the exception - bomb becomes solid
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

func apply_cornering_assist(move_dir: Vector2, tile_center: Vector2) -> Vector2:
	"""Apply automatic cornering assistance (wall hugging) for smooth navigation"""
	var speed = Constants.BASE_SPEED * Constants.RUN_MULTIPLIER
	var movement = move_dir * speed
	
	# Apply cornering assist - nudge toward corridor center when slightly off-axis
	if abs(move_dir.x) > 0.5:  # Moving horizontally
		var vertical_offset = position.y - tile_center.y
		if abs(vertical_offset) < Constants.CORNER_ASSIST_THRESHOLD:
			# Nudge toward horizontal center
			var nudge_speed = speed * Constants.CORNER_ASSIST_SPEED_MULTIPLIER
			movement.y = -sign(vertical_offset) * min(abs(vertical_offset), nudge_speed)
	
	elif abs(move_dir.y) > 0.5:  # Moving vertically
		var horizontal_offset = position.x - tile_center.x
		if abs(horizontal_offset) < Constants.CORNER_ASSIST_THRESHOLD:
			# Nudge toward vertical center
			var nudge_speed = speed * Constants.CORNER_ASSIST_SPEED_MULTIPLIER
			movement.x = -sign(horizontal_offset) * min(abs(horizontal_offset), nudge_speed)
	
	return movement

func snap_to_center(tile_center: Vector2) -> Vector2:
	"""Gradually move to tile center when player is idle"""
	var offset = tile_center - position
	var distance = offset.length()
	
	# If very close, snap exactly and stop
	if distance < Constants.SNAP_THRESHOLD:
		position = tile_center
		return Vector2.ZERO
	
	# Move toward center at snap speed
	return offset.normalized() * Constants.SNAP_TO_CENTER_SPEED

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
