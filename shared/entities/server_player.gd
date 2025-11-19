extends CharacterBody2D
class_name ServerPlayer

const ServerBomb = preload("res://shared/entities/server_bomb.gd")

# Server-authoritative player character
# Handles movement, collision, bomb placement, and power-ups
# Uses Godot's built-in collision system with exceptions
# Implements corner sliding for smoother navigation

const Constants = preload("res://shared/constants.gd")
const ServerPowerUpScript = preload("res://shared/entities/server_powerup.gd")
const InputBufferScript = preload("res://shared/entities/input_buffer.gd")

var player_id: String = ""
var peer_id: int = 0
var player_name: String = ""
var username: String = ""
var input_direction := Vector2.ZERO
var last_move_direction := Vector2.ZERO  # The last direction we successfully moved (persists when stationary)
var place_bomb_requested := false
var bombs_placed := 0
var max_bombs := 1
var bomb_range := 2
var speed_multiplier := 1.0  # Power-up speed multiplier
var is_dead := false
var is_bot := false
var bot_personality := ""
var debug_check_tile := Vector2i.ZERO  # Tile being checked for diagonal (for client debug)
var debug_blocking_tile := Vector2i.ZERO  # The blocking tile (for debug visualization)

# Advanced abilities (Phase 2)
var has_bomb_kicker := false  # Can kick bombs
var has_power_glove := false  # Can pick up and throw bombs

# Power Glove state
var carried_bomb: Node = null  # Reference to bomb being carried
var action_button_pressed := false  # Track action button state for throw timing
var is_picking_up_bomb := false  # True during pickup animation
var pickup_animation_time := 0.0  # Time elapsed in pickup animation
var pickup_animation_direction := Vector2.DOWN  # Direction player is facing during pickup

const PICKUP_ANIMATION_DURATION = 0.3  # Duration of pickup animation in seconds (fast like SBomberman)

# Collision exceptions for bombs we've placed
var collision_exceptions := []

# LimboAI integration for player-controlled entities (optional)
var input_buffer: InputBufferScript = null  # Input buffering for BT-based player control
var bt_player = null  # Optional: LimboAI BT player for input processing

# ShapeCast2D nodes for checking directions
var shape_cast_desired: ShapeCast2D
var shape_cast_perp1: ShapeCast2D
var shape_cast_perp2: ShapeCast2D
var kick_detector: ShapeCast2D

# Debug visualization
var debug_arrow: Polygon2D
var debug_tiles: Dictionary = {}  # Store debug tile overlays
var debug_raycast_line: Line2D  # Visualize the raycast

# Note: COLLISION_CHECK_DISTANCE moved to GameConfig for dynamic scaling
const ENABLE_GRID_SNAPPING = true  # Re-enabled with matching client prediction
const ENABLE_CORNER_SLIDING = true  # Toggle manual corner sliding logic

func _ready():
	# Set collision layers: players on layer 2, collide with walls (1), bombs (4), and powerups (16)
	collision_layer = Constants.COLLISION_LAYER_PLAYERS
	collision_mask = Constants.COLLISION_LAYER_WALLS | Constants.COLLISION_LAYER_BOMBS | Constants.COLLISION_LAYER_POWERUPS

	# Set up collision shape - USE RECTANGLE for precise collision
	var collision_shape = CollisionShape2D.new()
	var shape = RectangleShape2D.new()
	shape.size = Vector2(GameConfig.PLAYER_HALF_WIDTH * 2, GameConfig.PLAYER_HALF_WIDTH * 2)  # Dynamic size based on tile
	collision_shape.shape = shape
	add_child(collision_shape)

	# Set up ShapeCast2D nodes for collision checking
	_setup_shape_casts()

	# Set up debug arrow
	_setup_debug_arrow()

	# Set up debug raycast line
	_setup_debug_raycast()

func _setup_debug_arrow():
	"""Create a visual arrow to show facing direction"""
	debug_arrow = Polygon2D.new()

	# Smaller arrow shape pointing right
	var arrow_points = PackedVector2Array([
		Vector2(0, -8),       # Top left
		Vector2(25, 0),       # Tip (pointing right)
		Vector2(0, 8),        # Bottom left
		Vector2(6, 0)         # Inner notch
	])

	debug_arrow.polygon = arrow_points
	debug_arrow.color = Color(1, 0.5, 0, 0.8)  # Orange, semi-transparent
	debug_arrow.z_index = 100
	debug_arrow.z_as_relative = false
	debug_arrow.position = Vector2(0, -35)
	add_child(debug_arrow)

func _setup_debug_raycast():
	"""ShapeCast2D will handle visualization - this is kept for compatibility"""
	pass  # Visualization now done by ShapeCast2D

func _setup_shape_casts():
	"""Create ShapeCast2D nodes for checking collisions in different directions"""
	# Create shape for casting
	var cast_shape = RectangleShape2D.new()
	cast_shape.size = Vector2(GameConfig.PLAYER_HALF_WIDTH * 2, GameConfig.PLAYER_HALF_WIDTH * 2)  # Dynamic size

	# ShapeCast for desired direction (check walls and bombs, not other players)
	shape_cast_desired = ShapeCast2D.new()
	shape_cast_desired.shape = cast_shape
	shape_cast_desired.collision_mask = Constants.COLLISION_LAYER_WALLS | Constants.COLLISION_LAYER_BOMBS
	shape_cast_desired.enabled = true  # Keep enabled for debugging
	shape_cast_desired.exclude_parent = true  # Don't collide with self!
	add_child(shape_cast_desired)
	# Explicitly exclude this player's physics body
	shape_cast_desired.add_exception(self)

	# ShapeCast for kick detection
	kick_detector = ShapeCast2D.new()
	kick_detector.shape = cast_shape
	kick_detector.collision_mask = Constants.COLLISION_LAYER_BOMBS
	kick_detector.enabled = true
	add_child(kick_detector)

	# ShapeCast for perpendicular direction 1
	shape_cast_perp1 = ShapeCast2D.new()
	shape_cast_perp1.shape = cast_shape
	shape_cast_perp1.collision_mask = Constants.COLLISION_LAYER_WALLS | Constants.COLLISION_LAYER_BOMBS
	shape_cast_perp1.enabled = false
	add_child(shape_cast_perp1)

	# ShapeCast for perpendicular direction 2
	shape_cast_perp2 = ShapeCast2D.new()
	shape_cast_perp2.shape = cast_shape
	shape_cast_perp2.collision_mask = Constants.COLLISION_LAYER_WALLS | Constants.COLLISION_LAYER_BOMBS
	shape_cast_perp2.enabled = false
	add_child(shape_cast_perp2)

func _check_direction_clear(direction: Vector2) -> bool:
	"""Check if movement in a given direction is clear using ShapeCast2D"""
	if direction.length() < 0.1:
		return false

	# Use ShapeCast2D for collision detection
	var motion = direction.normalized() * GameConfig.COLLISION_CHECK_DISTANCE

	# Add collision exceptions (bombs)
	for bomb in collision_exceptions:
		if is_instance_valid(bomb):
			shape_cast_desired.add_exception(bomb)

	# Configure and perform shape cast
	shape_cast_desired.target_position = motion
	shape_cast_desired.force_shapecast_update()

	var collision_detected = shape_cast_desired.is_colliding()

	# Store collision data BEFORE clearing exceptions (otherwise collision info is lost!)
	if collision_detected:
		# Get the collision point and calculate which tile was hit
		var collision_point = shape_cast_desired.get_collision_point(0)
		var collision_normal = shape_cast_desired.get_collision_normal(0)
		var collider = shape_cast_desired.get_collider(0)

		print("COLLISION DETECTED! Collider: ", collider, " Type: ", collider.get_class() if collider else "null", " Name: ", collider.name if collider else "null")

		# Sample slightly inside the collider to get the blocking tile
		var sample_point = collision_point - collision_normal * 0.5

		debug_blocking_tile = Vector2i(
			int(floor(sample_point.x / GameConfig.TILE_SIZE)),
			int(floor(sample_point.y / GameConfig.TILE_SIZE))
		)

	# Clear bomb exceptions AFTER getting collision data
	shape_cast_desired.clear_exceptions()
	# Re-add the permanent self-exception (clear_exceptions removes ALL exceptions)
	shape_cast_desired.add_exception(self)

	# Return true if NO collision was detected (path is clear)
	return not collision_detected

func _get_perpendicular_directions(direction: Vector2) -> Array:
	"""Get the two perpendicular directions for a given direction"""
	if direction.length() < 0.1:
		return [Vector2.ZERO, Vector2.ZERO]

	# For cardinal directions, return the other two cardinal directions
	if abs(direction.x) > abs(direction.y):
		# Moving horizontally, perpendiculars are up and down
		return [Vector2.UP, Vector2.DOWN]
	else:
		# Moving vertically, perpendiculars are left and right
		return [Vector2.LEFT, Vector2.RIGHT]

func _can_corner_slide(blocked_direction: Vector2) -> Vector2:
	"""Check if we can slide around a corner when blocked.
	Returns the direction we can slide in, or Vector2.ZERO if no slide possible.

	Logic:
	- If blocked moving horizontally (LEFT/RIGHT), check if near top/bottom edge of tile
	- If blocked moving vertically (UP/DOWN), check if near left/right edge of tile
	- If near an edge, try moving in that perpendicular direction
	"""

	# Get the center of the BLOCKING tile (not our current tile)
	var blocking_tile_center = Vector2(
		debug_blocking_tile.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
		debug_blocking_tile.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
	)

	# Calculate our offset from the blocking tile's center
	var offset_from_blocking = position - blocking_tile_center

	# Also get our current tile center for reference
	var current_tile_center = get_current_tile_center()
	var offset_from_current = position - current_tile_center

	# Edge threshold: within 0.5 of tile edge means we can slide
	# For a 64px tile, half is 32px, so edge_threshold should be around 24-28px
	var edge_threshold = GameConfig.TILE_SIZE / 4.0  # Within 8px of edge

	print("Blocked dir: ", blocked_direction)
	print("Blocking tile: ", debug_blocking_tile, " center: ", blocking_tile_center)
	print("Our position: ", position)
	print("Offset from blocking tile: ", offset_from_blocking)
	print("Offset from current tile: ", offset_from_current)
	print("Edge threshold: ", edge_threshold)

	# Blocked moving horizontally (LEFT or RIGHT)?
	if abs(blocked_direction.x) > 0.5:
		# Check if near TOP edge relative to blocking tile
		if offset_from_blocking.y < -edge_threshold:
			print("Near TOP edge, trying UP")
			# Near top, try sliding UP
			# BUT we need to check TWO things:
			# 1. Can we move UP from our current position?
			# 2. Is the tile ABOVE the blocking tile also walkable?
			var tile_above_blocking = Vector2i(debug_blocking_tile.x, debug_blocking_tile.y - 1)
			if _check_direction_clear(Vector2.UP) and is_tile_walkable(tile_above_blocking):
				print("  -> Both UP path and tile above blocking are clear!")
				return Vector2.UP
		# Check if near BOTTOM edge relative to blocking tile
		elif offset_from_blocking.y > edge_threshold:
			print("Near BOTTOM edge, trying DOWN")
			# Near bottom, try sliding DOWN
			# Same logic: check both DOWN path and tile below blocking tile
			var tile_below_blocking = Vector2i(debug_blocking_tile.x, debug_blocking_tile.y + 1)
			if _check_direction_clear(Vector2.DOWN) and is_tile_walkable(tile_below_blocking):
				print("  -> Both DOWN path and tile below blocking are clear!")
				return Vector2.DOWN

	# Blocked moving vertically (UP or DOWN)?
	elif abs(blocked_direction.y) > 0.5:
		# Check if near LEFT edge relative to blocking tile
		if offset_from_blocking.x < -edge_threshold:
			print("Near LEFT edge, trying LEFT")
			# Near left, try sliding LEFT
			# Check both LEFT path and tile to the left of blocking tile
			var tile_left_of_blocking = Vector2i(debug_blocking_tile.x - 1, debug_blocking_tile.y)
			if _check_direction_clear(Vector2.LEFT) and is_tile_walkable(tile_left_of_blocking):
				print("  -> Both LEFT path and tile left of blocking are clear!")
				return Vector2.LEFT
		# Check if near RIGHT edge relative to blocking tile
		elif offset_from_blocking.x > edge_threshold:
			print("Near RIGHT edge, trying RIGHT")
			# Near right, try sliding RIGHT
			# Check both RIGHT path and tile to the right of blocking tile
			var tile_right_of_blocking = Vector2i(debug_blocking_tile.x + 1, debug_blocking_tile.y)
			if _check_direction_clear(Vector2.RIGHT) and is_tile_walkable(tile_right_of_blocking):
				print("  -> Both RIGHT path and tile right of blocking are clear!")
				return Vector2.RIGHT

	# No slide possible
	return Vector2.ZERO

func _is_diagonal_blocked(_move_vec: Vector2, _input_vec: Vector2) -> bool:
	"""Check if we can slide using corner sliding logic

	The logic is simple:
	1. The blocking tile was already detected by _check_direction_clear() via raycast
	2. Calculate the desired_tile = blocking_tile + move_direction (facing)
	3. Check if the desired tile is physically reachable by sliding
	"""
	# The blocking tile was already set by _check_direction_clear() via actual physics raycast
	# Use that real collision data (stored in debug_blocking_tile)
	var blocking_tile = debug_blocking_tile

	# The desired tile is where we want to slide to
	# Formula: blocking_tile + move_direction (our facing direction)
	var desired_tile = Vector2i(
		blocking_tile.x + int(_move_vec.x),
		blocking_tile.y + int(_move_vec.y)
	)

	# Store for debug visualization
	debug_check_tile = desired_tile

	# Simple check: is the tile itself walkable?
	# If the desired tile is a wall, we definitely can't slide there
	if not is_tile_walkable(desired_tile):
		return true  # Blocked - tile is a wall

	# If the tile is walkable (empty), we can slide
	# The slide direction (_move_vec) is already checked as clear in the main logic
	return false

func _vector_to_facing(direction: Vector2) -> String:
	"""Convert direction Vector2 to facing string"""
	if direction.length() < 0.1:
		return "DOWN"  # Default facing

	if abs(direction.y) > abs(direction.x):
		return "UP" if direction.y < 0 else "DOWN"
	else:
		return "LEFT" if direction.x < 0 else "RIGHT"

func _physics_process(_delta):
	if is_dead:
		velocity = Vector2.ZERO
		# last_move_direction = Vector2.ZERO
		move_and_slide()
		return

	# --- NEW KICK DETECTION LOGIC ---
	if has_bomb_kicker and input_direction.length() > 0.1:
		kick_detector.target_position = input_direction.normalized() * (GameConfig.TILE_SIZE / 2.0)
		kick_detector.force_shapecast_update()

		if kick_detector.is_colliding():
			var collider = kick_detector.get_collider(0)
			if collider is ServerBomb and not (collider in collision_exceptions):
				print("[Player] Kick Detector found bomb: ", collider.name)
				collider.kick(input_direction)

	# Update pickup animation timer
	if is_picking_up_bomb:
		pickup_animation_time += _delta
		if pickup_animation_time >= PICKUP_ANIMATION_DURATION:
			is_picking_up_bomb = false
			pickup_animation_time = 0.0

	# Get the input direction (strict 4-way)
	var input_dir = get_4way_input()

	# Debug: Print input state every frame for a few seconds
	if Engine.get_process_frames() % 60 == 0:  # Every 60 frames (~1 second)
		print("[ServerPlayer DEBUG] ", username, " has_bomb_kicker=", has_bomb_kicker, " input_dir=", input_dir, " input_direction=", input_direction)

	if input_dir.length() < Constants.INPUT_DEADZONE:
		# No input - stop moving but keep last_move_direction
		velocity = Vector2.ZERO
		move_and_slide()
		return

	var final_direction := Vector2.ZERO

	# CHECK 1: Is the input_direction clear?
	var input_clear = _check_direction_clear(input_dir)
	var _input_blocking_tile = debug_blocking_tile  # Save the blocking tile from input check
	_is_diagonal_blocked(last_move_direction, input_dir)

	# print("Input dir: ", input_dir, " Clear: ", input_clear, " Colliding: ", shape_cast_desired.is_colliding())

	if input_clear:
		# Clear debug tiles when moving freely
		for tile_key in debug_tiles.keys():
			if is_instance_valid(debug_tiles[tile_key]):
				debug_tiles[tile_key].queue_free()
		debug_tiles.clear()

		# YES - Move in input direction and UPDATE last_move_direction
		final_direction = input_dir
	else:
		# Input direction blocked - try corner sliding
		var slide_direction = _can_corner_slide(input_dir)

		if slide_direction != Vector2.ZERO:
			# We can slide around the corner!
			final_direction = slide_direction
		#else:
		#	# Can't slide, try continuing in last_move_direction
		#	if _check_direction_clear(last_move_direction):
		#		final_direction = last_move_direction
		else:
			# Completely blocked, reset
			last_move_direction = input_dir

	# Update last_move_direction if we're actively moving
	if final_direction.length() > 0:
		last_move_direction = final_direction

	# Update debug arrow rotation
	_update_debug_arrow()

	if final_direction.length() > 0:
		var speed = GameConfig.BASE_SPEED * Constants.RUN_MULTIPLIER * speed_multiplier
		velocity = final_direction * speed

		# Auto-align to grid: Add correction to movement vector
		# When moving horizontally, gradually align vertically
		# When moving vertically, gradually align horizontally
		if ENABLE_GRID_SNAPPING:
			var tile_center = get_current_tile_center()
			var offset_from_center = tile_center - position

			if abs(final_direction.x) > 0.5:
				# Moving horizontally - align vertically to grid
				if abs(offset_from_center.y) > GameConfig.SNAP_THRESHOLD:
					var correction_y = sign(offset_from_center.y) * GameConfig.SNAP_TO_CENTER_SPEED
					velocity.y += correction_y

			if abs(final_direction.y) > 0.5:
				# Moving vertically - align horizontally to grid
				if abs(offset_from_center.x) > GameConfig.SNAP_THRESHOLD:
					var correction_x = sign(offset_from_center.x) * GameConfig.SNAP_TO_CENTER_SPEED
					velocity.x += correction_x
	else:
		velocity = Vector2.ZERO

	var pos_before = position
	move_and_slide()
	var pos_after = position

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
			remove_collision_exception_with(bomb)
			collision_exceptions.remove_at(i)

func _update_debug_arrow():
	"""Update the debug arrow rotation based on last move direction"""
	if not debug_arrow:
		return

	var facing = _vector_to_facing(last_move_direction)
	var rotation_map = {
		"RIGHT": 0.0,
		"DOWN": PI / 2.0,
		"LEFT": PI,
		"UP": -PI / 2.0
	}

	if facing in rotation_map:
		debug_arrow.rotation = rotation_map[facing]

func _show_debug_tile(tile_pos: Vector2i, color: Color):
	"""Show a colored overlay on a tile for debugging"""
	var tile_key = "%d,%d" % [tile_pos.x, tile_pos.y]

	# Remove old debug tile if exists
	if debug_tiles.has(tile_key):
		debug_tiles[tile_key].queue_free()
		debug_tiles.erase(tile_key)

	# Create new debug overlay with border
	var debug_rect = ColorRect.new()
	debug_rect.size = Vector2(GameConfig.TILE_SIZE, GameConfig.TILE_SIZE)
	debug_rect.color = color
	debug_rect.position = Vector2(
		tile_pos.x * GameConfig.TILE_SIZE,
		tile_pos.y * GameConfig.TILE_SIZE
	)
	debug_rect.z_index = 99

	# Add to scene
	get_parent().add_child(debug_rect)
	debug_tiles[tile_key] = debug_rect

	# Auto-remove after a short time
	await get_tree().create_timer(0.1).timeout
	if is_instance_valid(debug_rect):
		debug_rect.queue_free()
	if debug_tiles.has(tile_key):
		debug_tiles.erase(tile_key)

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
	var tile_x = floor(position.x / GameConfig.TILE_SIZE)
	var tile_y = floor(position.y / GameConfig.TILE_SIZE)
	return Vector2(
		tile_x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
		tile_y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
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
		int(floor(position.x / GameConfig.TILE_SIZE)),
		int(floor(position.y / GameConfig.TILE_SIZE))
	)

func set_input(input_x: float, input_y: float):
	"""Set movement input direction.
	Can be called directly or via input buffer for BT-based control."""
	input_direction = Vector2(input_x, input_y)

func queue_input(input_data: Dictionary) -> void:
	"""Queue input for BT-based processing.
	Used when LimboAI input buffer is enabled."""
	if input_buffer:
		input_buffer.push_input(input_data)
	else:
		# Fallback to direct input if buffer not initialized
		set_input(input_data.get("input_x", 0.0), input_data.get("input_y", 0.0))
		place_bomb_requested = input_data.get("place_bomb", false)
		action_button_pressed = input_data.get("action_pressed", false)

func initialize_input_buffer() -> void:
	"""Initialize input buffer for LimboAI-based player control."""
	if not input_buffer:
		input_buffer = InputBufferScript.new()

func request_bomb_placement():
	if is_dead:
		return
	place_bomb_requested = true

func request_action_press():
	"""Called when action button is pressed (for Power Glove pickup/throw)"""
	if is_dead:
		return
	action_button_pressed = true

func request_action_release():
	"""Called when action button is released (for Power Glove throw)"""
	action_button_pressed = false

func can_place_bomb() -> bool:
	if is_dead:
		return false
	return bombs_placed < max_bombs

# ============ POWER GLOVE SYSTEM ============

func try_pickup_bomb(bomb: Node) -> bool:
	"""Try to pick up a bomb with Power Glove (server-side)"""
	if not has_power_glove:
		return false

	if not is_instance_valid(bomb):
		return false

	if carried_bomb != null:
		return false  # Already carrying a bomb

	# Check if standing on the bomb's tile
	var player_tile = get_tile_position()
	var bomb_tile = bomb.get_tile_position()

	if player_tile != bomb_tile:
		return false  # Not on the same tile

	# Attempt pickup
	if bomb.pick_up(self):
		carried_bomb = bomb
		is_picking_up_bomb = true
		pickup_animation_time = 0.0
		pickup_animation_direction = last_move_direction if last_move_direction.length() > 0.1 else Vector2.DOWN
		print("[ServerPlayer] ", username, " picked up bomb ", bomb.bomb_id)
		return true

	return false

func throw_carried_bomb() -> bool:
	"""Throw the currently carried bomb (server-side)"""
	if not has_power_glove:
		return false

	if not is_instance_valid(carried_bomb):
		carried_bomb = null
		return false

	# Throw in the direction player is facing
	var throw_direction = last_move_direction
	if throw_direction.length() < 0.1:
		throw_direction = Vector2.DOWN  # Default direction if not moving

	if carried_bomb.throw_bomb(throw_direction):
		print("[ServerPlayer] ", username, " threw bomb ", carried_bomb.bomb_id, " in direction ", throw_direction)
		carried_bomb = null
		return true

	return false

func is_carrying_bomb() -> bool:
	"""Check if player is currently carrying a bomb"""
	return carried_bomb != null and is_instance_valid(carried_bomb)

func get_carried_bomb_offset() -> Vector2:
	"""Calculate the visual offset for carried bomb based on pickup animation or carry state.
	Mimics SBomberman's frame-by-frame bomb positioning during pickup animation.
	"""
	if not is_carrying_bomb():
		return Vector2.ZERO

	# Get facing direction for animation
	var facing_dir = pickup_animation_direction if is_picking_up_bomb else last_move_direction
	if facing_dir.length() < 0.1:
		facing_dir = Vector2.DOWN

	# Convert to direction string
	var direction = ""
	if abs(facing_dir.y) > abs(facing_dir.x):
		direction = "up" if facing_dir.y < 0 else "down"
	else:
		direction = "left" if facing_dir.x < 0 else "right"

	# Calculate animation frame (0, 1, or 2) based on animation progress
	var frame = 2  # Default to final frame (fully held overhead)
	if is_picking_up_bomb:
		var progress = pickup_animation_time / PICKUP_ANIMATION_DURATION
		frame = int(progress * 3.0)  # 3 frames total
		frame = clamp(frame, 0, 2)

	# Bomb position table from SBomberman (frame-by-frame positioning)
	# Each frame has position offset relative to player center
	var bomb_position_table = {
		"up": {
			0: Vector2(0, 0),      # Frame 0: at player center
			1: Vector2(0, -8),     # Frame 1: slightly above
			2: Vector2(0, -20)     # Frame 2: fully overhead
		},
		"down": {
			0: Vector2(0, 16),     # Frame 0: in front/below
			1: Vector2(0, -8),     # Frame 1: rising up
			2: Vector2(0, -20)     # Frame 2: fully overhead
		},
		"left": {
			0: Vector2(-10, 8),    # Frame 0: to the side
			1: Vector2(-16, 0),    # Frame 1: moving up and out
			2: Vector2(0, -24)     # Frame 2: fully overhead
		},
		"right": {
			0: Vector2(10, 8),     # Frame 0: to the side
			1: Vector2(16, 0),     # Frame 1: moving up and out
			2: Vector2(0, -24)     # Frame 2: fully overhead
		}
	}

	return bomb_position_table[direction][frame]

# ============ END POWER GLOVE SYSTEM ============

func add_bomb_collision_exception(bomb):
	if bomb in collision_exceptions:
		return

	print("[Player] Adding collision exception for bomb at ", bomb.get_tile_position() if is_instance_valid(bomb) else "invalid")
	collision_exceptions.append(bomb)

	if bomb.is_inside_tree():
		_apply_bomb_collision_exception(bomb)
	else:
		call_deferred("_apply_bomb_collision_exception", bomb)

func _apply_bomb_collision_exception(bomb):
	if not is_instance_valid(bomb):
		return
	if not bomb.is_inside_tree():
		call_deferred("_apply_bomb_collision_exception", bomb)
		return

	bomb.add_collision_exception_with(self)
	add_collision_exception_with(bomb)

func die():
	is_dead = true
	place_bomb_requested = false
	input_direction = Vector2.ZERO
	velocity = Vector2.ZERO
	# TODO: Play death animation
	# TODO: Respawn logic

func collect_powerup(powerup):
	"""Called when player collects a power-up"""
	match powerup.powerup_type:
		ServerPowerUpScript.PowerUpType.BOMB_INCREASE:
			max_bombs += 1
			print("[Player] ", username, " collected BOMB power-up! Max bombs: ", max_bombs)
		ServerPowerUpScript.PowerUpType.RANGE_INCREASE:
			bomb_range += 1
			print("[Player] ", username, " collected RANGE power-up! Range: ", bomb_range)
		ServerPowerUpScript.PowerUpType.SPEED_INCREASE:
			speed_multiplier += 0.2
			print("[Player] ", username, " collected SPEED power-up! Speed: ", speed_multiplier)
		ServerPowerUpScript.PowerUpType.BOMB_KICKER:
			has_bomb_kicker = true
			print("[Player] ", username, " collected BOMB KICKER!")
		ServerPowerUpScript.PowerUpType.POWER_GLOVE:
			has_power_glove = true
			print("[Player] ", username, " collected POWER GLOVE! (Phase 2 feature)")
		ServerPowerUpScript.PowerUpType.VIRUS:
			# TODO: Implement virus debuffs in Phase 2
			print("[Player] ", username, " collected VIRUS! (Phase 2 - no effect yet)")

func get_state() -> Dictionary:
	return {
		"player_id": player_id,
		"username": username,
		"is_bot": is_bot,
		"bot_personality": bot_personality,
		"position": {"x": position.x, "y": position.y},
		"velocity": {"x": velocity.x, "y": velocity.y},
		"facing": _vector_to_facing(last_move_direction),
		"is_dead": is_dead,
		"bombs_placed": bombs_placed,
		"max_bombs": max_bombs,
		"bomb_range": bomb_range,
		"speed_multiplier": speed_multiplier,
		"has_bomb_kicker": has_bomb_kicker,
		"has_power_glove": has_power_glove,
		"is_carrying_bomb": is_carrying_bomb(),
		"carried_bomb_id": carried_bomb.bomb_id if is_carrying_bomb() else "",
		"is_picking_up_bomb": is_picking_up_bomb,
		"pickup_animation_direction": {"x": pickup_animation_direction.x, "y": pickup_animation_direction.y},
		"last_move_direction": {"x": last_move_direction.x, "y": last_move_direction.y},
		"debug_check_tile": {"x": debug_check_tile.x, "y": debug_check_tile.y},
		"debug_blocking_tile": {"x": debug_blocking_tile.x, "y": debug_blocking_tile.y},
		"shape_cast_target": {"x": shape_cast_desired.target_position.x, "y": shape_cast_desired.target_position.y},
		"shape_cast_colliding": shape_cast_desired.is_colliding()
	}

func set_bot_metadata(personality: String) -> void:
	is_bot = true
	bot_personality = personality

func is_ai_bot() -> bool:
	return is_bot
