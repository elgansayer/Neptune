extends CharacterBody2D
class_name ServerPlayer

const ServerBombScript = preload("res://shared/entities/server_bomb.gd")
const PlayerStatsScript = preload("res://shared/resources/player_stats.gd")

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
var last_move_direction := Vector2.ZERO # The last direction we successfully moved (persists when stationary)
var place_bomb_requested := false
var bombs_placed := 0
var max_bombs := 1 # Saturn Bomberman: Start with 1 bomb, collect powerups for more
var bomb_range := 1 # CLASSIC: Start with range 1 to allow escape from spawn corners
var speed_multiplier := 1.0 # Power-up speed multiplier (display/sync only - actual speed uses accumulator)
var is_dead := false
var is_spectator := false # Player is eliminated and watching the match
var is_bot := false
var bot_personality := ""
var debug_check_tile := Vector2i.ZERO # Tile being checked for diagonal (for client debug)
var debug_blocking_tile := Vector2i.ZERO # The blocking tile (for debug visualization)

# === SATURN BOMBERMAN MOVEMENT SYSTEM ===
# Sub-pixel accumulator for deterministic, integer-based movement
var skate_count: int = 0 # Number of roller skate power-ups collected
var sub_pixel_accumulator: int = 0 # Range: 0 to 255, overflows at 256

# Advanced abilities (Phase 2)
var has_bomb_kicker := false # Can kick bombs
var has_power_glove := false # Can pick up and throw bombs
var has_line_bomb := false   # Can place all bombs in a line

# === BOMB TYPE SYSTEM (Saturn Bomberman) ===
# 0 = Normal, 1 = Remote (manual detonate), 2 = Power (pierce blocks), 3 = Rubber (bounce)
var bomb_type: int = 0
const BOMB_TYPE_NORMAL := 0
const BOMB_TYPE_REMOTE := 1
const BOMB_TYPE_POWER := 2
const BOMB_TYPE_RUBBER := 3

# === SATURN BOMBERMAN VIRUS (SKULL) SYSTEM ===
# Virus effects from collecting skull items - can be transferred between players!
enum VirusType {
	NONE = 0,
	SPEEDSTER = 1,        # Speed maxed out (can be good or dangerous!)
	SLOWPOKE = 2,         # Speed reduced to minimum
	DIARRHOEA = 3,        # Bombs auto-place constantly
	CONSTIPATION = 4,     # Cannot place bombs
	SMALL_FLAME = 5,      # Bomb range forced to 1
	UNSTOPPABLE = 6,      # Player can't stop moving (uses last direction if no input)
	REVERSE = 7,          # Controls reversed
	HASTY_FUSE = 8,       # Bombs explode in ~1 second
	LEISURELY_FUSE = 9,   # Bombs have 5-6 second fuse
}
var active_virus: VirusType = VirusType.NONE
var virus_end_time: float = 0.0  # When virus expires (Time.get_ticks_msec())
const VIRUS_DURATION_MS: float = 12000.0  # 12 seconds (Saturn Bomberman spec)
var last_nonzero_direction: Vector2 = Vector2.DOWN  # For UNSTOPPABLE virus

# Power Glove state
var carried_bomb: Node = null # Reference to bomb being carried
var action_button_pressed := false # Track action button state for throw timing
var is_picking_up_bomb := false # True during pickup animation
var pickup_animation_time := 0.0 # Time elapsed in pickup animation
var pickup_animation_direction := Vector2.DOWN # Direction player is facing during pickup

const PICKUP_ANIMATION_DURATION = 0.3 # Duration of pickup animation in seconds (fast like SBomberman)

# Collision exceptions for bombs we've placed
var collision_exceptions := []

# LimboAI integration for player-controlled entities (optional)
var input_buffer: InputBufferScript = null # Input buffering for BT-based player control
var bt_player = null # Optional: LimboAI BT player for input processing

# ShapeCast2D nodes for checking directions (defined in ServerPlayer.tscn)
@onready var shape_cast_desired: ShapeCast2D = $ShapeCastDesired
@onready var shape_cast_perp1: ShapeCast2D = $ShapeCastPerp1
@onready var shape_cast_perp2: ShapeCast2D = $ShapeCastPerp2
@onready var kick_detector: ShapeCast2D = $KickDetector

# Debug visualization (defined in ServerPlayer.tscn)
@onready var debug_arrow: Polygon2D = $DebugArrow
@onready var debug_path_line: Line2D = $DebugPathLine
@onready var debug_target_line: Line2D = $DebugTargetLine

var debug_tiles: Dictionary = {} # Store debug tile overlays
var debug_raycast_line: Line2D # Kept for compatibility
var debug_target_center: Vector2 = Vector2.ZERO
var debug_target_active: bool = false

# Note: COLLISION_CHECK_DISTANCE moved to GameConfig for dynamic scaling
const ENABLE_GRID_SNAPPING = true # Re-enabled with matching client prediction
const ENABLE_CORNER_SLIDING = true # Toggle manual corner sliding logic

func _ready():
	# Collision layers and shapes are already set in ServerPlayer.tscn
	# Update shapes to use dynamic GameConfig values at runtime
	_update_collision_shape_sizes()
	
	# Add self-exception to shape casts
	if shape_cast_desired:
		shape_cast_desired.add_exception(self)

func _update_collision_shape_sizes():
	"""Update collision shapes to match current GameConfig values"""
	var size = Vector2(GameConfig.PLAYER_HALF_WIDTH * 2, GameConfig.PLAYER_HALF_WIDTH * 2)
	
	# Update collision shape
	var collision_shape = $CollisionShape2D
	if collision_shape and collision_shape.shape:
		collision_shape.shape.size = size
	
	# Update shape cast shapes
	for cast in [shape_cast_desired, shape_cast_perp1, shape_cast_perp2, kick_detector]:
		if cast and cast.shape:
			cast.shape.size = size

func _check_direction_clear(direction: Vector2) -> bool:
	"""Check if movement in a given direction is clear using ShapeCast2D"""
	if direction.length() < 0.1:
		return false

	# Use ShapeCast2D for collision detection
	var motion = direction.normalized() * GameConfig.COLLISION_CHECK_DISTANCE
	
	# DEBUG: Log direction checking
	if is_bot and Engine.get_physics_frames() % 60 == 0:
		print("[_check_direction_clear] Bot at ", position, " checking direction ", direction, " motion=", motion)

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

		print("COLLISION DETECTED! Player at ", position, " Collider: ", collider, " at point: ", collision_point, " Name: ", collider.name if collider else "null")

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

	# Saturn Bomberman corner correction tolerance: ~5px at 16px tile size
	# This allows players to slide around corners when within this distance of an edge
	var edge_threshold = GameConfig.CORNER_ASSIST_THRESHOLD

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
		return true # Blocked - tile is a wall

	# If the tile is walkable (empty), we can slide
	# The slide direction (_move_vec) is already checked as clear in the main logic
	return false

func _vector_to_facing(direction: Vector2) -> String:
	"""Convert direction Vector2 to facing string"""
	if direction.length() < 0.1:
		return "DOWN" # Default facing

	if abs(direction.y) > abs(direction.x):
		return "UP" if direction.y < 0 else "DOWN"
	else:
		return "LEFT" if direction.x < 0 else "RIGHT"

func _physics_process(_delta):
	if Engine.get_physics_frames() % 300 == 0: # Log every 5 seconds
		print("[ServerPlayer] _physics_process running. Version: DEBUG-DIAGNOSE-5")
	
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
			if collider.get_script() == ServerBombScript and not (collider in collision_exceptions):
				print("[Player] Kick Detector found bomb: ", collider.name)
				collider.kick(input_direction)

	# Update pickup animation timer
	if is_picking_up_bomb:
		pickup_animation_time += _delta
		if pickup_animation_time >= PICKUP_ANIMATION_DURATION:
			is_picking_up_bomb = false
			pickup_animation_time = 0.0

	# Get the input direction (strict 4-way)
	# Apply virus effects to input direction
	var raw_input = get_4way_input()
	var input_dir = get_input_direction_with_virus(raw_input)
	var has_pending_target = debug_target_active
	var offset_to_target = Vector2.ZERO
	if has_pending_target:
		offset_to_target = debug_target_center - position
	var inside_target_hint = has_pending_target and abs(offset_to_target.x) <= GameConfig.TILE_SIZE * 0.5 + 0.5 and abs(offset_to_target.y) <= GameConfig.TILE_SIZE * 0.5 + 0.5

	# Debug: Print input state every frame for a few seconds
	if Engine.get_process_frames() % 60 == 0: # Every 60 frames (~1 second)
		pass # print("[ServerPlayer DEBUG] ", username, " has_bomb_kicker=", has_bomb_kicker, " input_dir=", input_dir, " input_direction=", input_direction)
	if input_dir.length() < Constants.INPUT_DEADZONE:
		# No input - stop moving but keep last_move_direction
		if inside_target_hint and offset_to_target.length() > 1.0:
			print("[ServerPlayer] WARNING: target offset %s but no input for %s (raw_input=%s)" % [offset_to_target, username, input_direction])
		velocity = Vector2.ZERO
		# Disabled: Aggressive snapping causes visible jerky movement when bots hide
		# if ENABLE_GRID_SNAPPING and is_bot:
		# 	_snap_bot_to_tile_center()
		move_and_slide()
		return

	var final_direction := Vector2.ZERO

	# CHECK 1: Is the input_direction clear?
	var input_clear = _check_direction_clear(input_dir)
	var _input_blocking_tile = debug_blocking_tile # Save the blocking tile from input check
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
		if inside_target_hint and offset_to_target.length() > 1.0:
			print("[ServerPlayer] WARNING: desired dir %s blocked while target offset %s remains for %s" % [input_dir, offset_to_target, username])
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
	if inside_target_hint and offset_to_target.length() > 1.0 and final_direction.length() < 0.1:
		print("[ServerPlayer] WARNING: no movement direction while target offset %s persists for %s" % [offset_to_target, username])

	if final_direction.length() > 0:
		# === SATURN BOMBERMAN MOVEMENT SYSTEM ===
		# Calculate pixels to move this frame using accumulator model
		var saturn_result = GameConfig.calculate_saturn_movement(skate_count, sub_pixel_accumulator)
		var pixels_to_move: int = saturn_result[0]
		sub_pixel_accumulator = saturn_result[1]
		
		# Scale pixels by tile size ratio and convert to velocity (pixels per second)
		# At 64px tiles (scale 4x): 1 Saturn pixel = 4 actual pixels
		# Velocity = pixels_per_frame * scale_factor * 60 fps
		var scaled_pixels_per_frame: float = float(pixels_to_move) * GameConfig.scale_factor
		var base_velocity_magnitude: float = scaled_pixels_per_frame * 60.0
		
		# Apply virus speed modifier (SLOWPOKE = 0.3x, SPEEDSTER = 2.0x)
		base_velocity_magnitude *= get_virus_speed_modifier()
		
		velocity = final_direction * base_velocity_magnitude

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
		# Reset accumulator when not moving (Saturn behavior)
		sub_pixel_accumulator = 0

	var _pos_before = position
	var pre_vel = velocity
	
	# DEBUG: Log velocity for bots
	if is_bot and Engine.get_physics_frames() % 60 == 0:
		print("[ServerPlayer DEBUG] ", username, " velocity=", velocity, " speed=", velocity.length(), " expected=", GameConfig.BASE_SPEED)
	
	move_and_slide()
	var _pos_after = position
	
	# DEBUG: Log bot position after move_and_slide
	if is_bot and input_direction.length() > 0.1:
		var delta_pos = _pos_after - _pos_before
		if pre_vel.length() > 1.0 and delta_pos.length() < 0.01:
			print("[POS DEBUG] frame=", Engine.get_physics_frames(), " ", username, " BLOCKED! pre_vel=", pre_vel, " delta=", delta_pos, " pos=", position, " input=", input_direction)
		else:
			print("[POS DEBUG] frame=", Engine.get_physics_frames(), " ", username, " pos=", position, " vel=", pre_vel, " delta=", delta_pos, " input=", input_direction)
	
	if has_pending_target:
		var post_move_offset = debug_target_center - position
		var still_inside_tile = abs(post_move_offset.x) <= GameConfig.TILE_SIZE * 0.5 + 0.5 and abs(post_move_offset.y) <= GameConfig.TILE_SIZE * 0.5 + 0.5
		if still_inside_tile and post_move_offset.length() > 1.0 and velocity.length() < 1.0 and final_direction.length() > 0.1:
			print("[ServerPlayer] WARNING: velocity stalled (|v|=%.2f) with desired %s while offset %s for %s" % [velocity.length(), final_direction, post_move_offset, username])
	
	# Debug collisions
	if is_bot and get_slide_collision_count() > 0:
		for i in range(get_slide_collision_count()):
			var collision = get_slide_collision(i)
			var collider = collision.get_collider()
			print("[ServerPlayer] Bot ", username, " collided with ", collider.name if collider else "null", " at ", collision.get_position())

	# Clear collision exceptions when player is no longer overlapping bomb
	for i in range(collision_exceptions.size() - 1, -1, -1):
		var bomb = collision_exceptions[i]
		if not is_instance_valid(bomb):
			collision_exceptions.remove_at(i)
			continue

		# Check if we are physically clear of the bomb
		# We need to be far enough away that our collision shapes don't overlap
		# Player radius ~7, Bomb radius ~8. Sum = 15.
		# Use a safe distance of 16.0 (one full tile) to be sure.
		var dist = position.distance_to(bomb.position)
		var safe_distance = GameConfig.TILE_SIZE * 1.1 # 16 * 1.1 = 17.6px
		
		if dist > safe_distance:
			print("[Player] Removing collision exception for bomb at ", bomb.get_tile_position(), " (dist: ", dist, ")")
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
		"UP": - PI / 2.0
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

func _snap_bot_to_tile_center():
	var tile_center = get_current_tile_center()
	var offset = tile_center - position
	var snap_threshold = GameConfig.TILE_SIZE * 0.49
	# Only snap if we're still inside the tile (offset limited)
	if abs(offset.x) <= snap_threshold and abs(offset.y) <= snap_threshold:
		position = tile_center

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
		return true # Assume walkable if we can't check

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
	var new_input = Vector2(input_x, input_y)
	
	# DEBUG: Log ALL input changes for bots
	if is_bot and new_input != input_direction:
		print("[ServerPlayer.set_input] Bot %s input changing: %s -> %s" % [username, input_direction, new_input])
	
	input_direction = new_input


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
	# CONSTIPATION virus prevents placing bombs
	if active_virus == VirusType.CONSTIPATION:
		return false
	return bombs_placed < max_bombs

func update_virus(current_time_msec: float) -> void:
	"""Check if virus has expired and clear it"""
	if active_virus != VirusType.NONE and current_time_msec >= virus_end_time:
		print("[Player] ", username, " virus EXPIRED (was ", VirusType.keys()[active_virus], ")")
		clear_virus()

func apply_virus(virus_type: VirusType) -> void:
	"""Apply a virus effect from skull pickup or transfer"""
	active_virus = virus_type
	virus_end_time = Time.get_ticks_msec() + VIRUS_DURATION_MS
	print("[Player] ", username, " INFECTED with ", VirusType.keys()[virus_type], " for ", VIRUS_DURATION_MS/1000.0, "s")
	
	# Apply immediate effects
	match virus_type:
		VirusType.SLOWPOKE:
			# Speed is handled in movement calculation
			pass
		VirusType.SPEEDSTER:
			# Speed is handled in movement calculation
			pass
		VirusType.REVERSE:
			# Input reversal handled in input processing
			pass
		VirusType.UNSTOPPABLE:
			# Uses last_nonzero_direction when input is zero
			pass
		VirusType.SMALL_FLAME:
			# Range is forced to 1 in get_effective_bomb_range()
			pass
		# Other viruses handled in their respective systems

func clear_virus() -> void:
	"""Remove active virus"""
	active_virus = VirusType.NONE
	virus_end_time = 0.0

func transfer_virus_to(other_player: ServerPlayer) -> bool:
	"""Transfer virus to another player on collision (tag mechanic)
	Returns true if virus was successfully transferred"""
	if active_virus == VirusType.NONE:
		return false
	if other_player.is_dead:
		return false
	
	# Transfer the virus
	var transferred_virus = active_virus
	clear_virus()
	other_player.apply_virus(transferred_virus)
	print("[Virus] ", username, " transferred ", VirusType.keys()[transferred_virus], " to ", other_player.username)
	return true

func get_virus_speed_modifier() -> float:
	"""Get speed modifier based on active virus"""
	match active_virus:
		VirusType.SLOWPOKE:
			return 0.3  # 30% speed
		VirusType.SPEEDSTER:
			return 2.0  # 200% speed (dangerous!)
		_:
			return 1.0

func should_auto_place_bomb() -> bool:
	"""DIARRHOEA virus causes automatic bomb placement"""
	return active_virus == VirusType.DIARRHOEA

func get_bomb_fuse_time() -> float:
	"""Get bomb timer based on virus status"""
	match active_virus:
		VirusType.HASTY_FUSE:
			return 1.0  # ~1 second fuse!
		VirusType.LEISURELY_FUSE:
			return randf_range(5.0, 6.0)  # 5-6 second fuse
		_:
			return 3.0  # Normal 3 second fuse

func get_effective_bomb_range() -> int:
	"""Get effective bomb range (affected by SMALL_FLAME virus)"""
	if active_virus == VirusType.SMALL_FLAME:
		return 1  # Forced to minimum range
	return bomb_range

func get_input_direction_with_virus(raw_direction: Vector2) -> Vector2:
	"""Apply virus effects to input direction:
	- REVERSE: inverts controls
	- UNSTOPPABLE: uses last non-zero direction if input is zero
	"""
	var direction = raw_direction
	
	# Track last non-zero direction for UNSTOPPABLE
	if raw_direction.length() > 0.1:
		last_nonzero_direction = raw_direction.normalized()
	
	# REVERSE: invert controls
	if active_virus == VirusType.REVERSE:
		direction = -direction
	
	# UNSTOPPABLE: can't stop moving - use last direction if no input
	if active_virus == VirusType.UNSTOPPABLE and direction.length() < 0.1:
		direction = last_nonzero_direction
	
	return direction

# ============ POWER GLOVE SYSTEM ============

func try_pickup_bomb(bomb: Node) -> bool:
	"""Try to pick up a bomb with Power Glove (server-side)"""
	if not has_power_glove:
		return false

	if not is_instance_valid(bomb):
		return false

	if carried_bomb != null:
		return false # Already carrying a bomb

	# Check if standing on the bomb's tile
	var player_tile = get_tile_position()
	var bomb_tile = bomb.get_tile_position()

	if player_tile != bomb_tile:
		return false # Not on the same tile

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
		throw_direction = Vector2.DOWN # Default direction if not moving

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
	var frame = 2 # Default to final frame (fully held overhead)
	if is_picking_up_bomb:
		var progress = pickup_animation_time / PICKUP_ANIMATION_DURATION
		frame = int(progress * 3.0) # 3 frames total
		frame = clamp(frame, 0, 2)

	# Bomb position table from SBomberman (frame-by-frame positioning)
	# Each frame has position offset relative to player center
	var bomb_position_table = {
		"up": {
			0: Vector2(0, 0), # Frame 0: at player center
			1: Vector2(0, -8), # Frame 1: slightly above
			2: Vector2(0, -20) # Frame 2: fully overhead
		},
		"down": {
			0: Vector2(0, 16), # Frame 0: in front/below
			1: Vector2(0, -8), # Frame 1: rising up
			2: Vector2(0, -20) # Frame 2: fully overhead
		},
		"left": {
			0: Vector2(-10, 8), # Frame 0: to the side
			1: Vector2(-16, 0), # Frame 1: moving up and out
			2: Vector2(0, -24) # Frame 2: fully overhead
		},
		"right": {
			0: Vector2(10, 8), # Frame 0: to the side
			1: Vector2(16, 0), # Frame 1: moving up and out
			2: Vector2(0, -24) # Frame 2: fully overhead
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
	is_spectator = true # Player becomes a spectator upon death
	place_bomb_requested = false
	input_direction = Vector2.ZERO
	velocity = Vector2.ZERO
	# TODO: Play death animation
	# Note: No respawn in Last Man Standing mode

func collect_powerup(powerup):
	"""Called when player collects a power-up (server-authoritative)
	
	Applies Saturn Bomberman stat limits and logs collection.
	Stats are clamped automatically by the setter functions.
	"""
	var type = powerup.powerup_type
	var type_name = ServerPowerUpScript.get_display_name(type)
	
	match type:
		# === STAT INCREASE ITEMS ===
		ServerPowerUpScript.PowerUpType.BOMB_INCREASE:
			var old_val = max_bombs
			max_bombs = mini(max_bombs + 1, Constants.BOMB_MAX)
			var changed = max_bombs != old_val
			print("[Player] ", username, " collected BOMB power-up! ", old_val, " -> ", max_bombs, 
				" (max: ", Constants.BOMB_MAX, ")", " changed=" if changed else " (already max)")
		
		ServerPowerUpScript.PowerUpType.RANGE_INCREASE:
			var old_val = bomb_range
			var max_range = Constants.FIRE_MAX  # TODO: Use FIRE_MAX_FULL if has_full_fire
			bomb_range = mini(bomb_range + 1, max_range)
			var changed = bomb_range != old_val
			print("[Player] ", username, " collected FIRE power-up! ", old_val, " -> ", bomb_range,
				" (max: ", max_range, ")", " changed=" if changed else " (already max)")
		
		ServerPowerUpScript.PowerUpType.SPEED_INCREASE:
			var old_val = skate_count
			skate_count = mini(skate_count + 1, GameConfig.SATURN_MAX_SKATES)
			speed_multiplier = GameConfig.get_skate_speed_multiplier(skate_count)
			var changed = skate_count != old_val
			print("[Player] ", username, " collected SPEED power-up! ", old_val, " -> ", skate_count,
				" skates (", speed_multiplier, "x)", " changed=" if changed else " (already max)")
		
		# === ABILITY ITEMS ===
		ServerPowerUpScript.PowerUpType.BOMB_KICKER:
			var was_enabled = has_bomb_kicker
			has_bomb_kicker = true
			print("[Player] ", username, " collected BOMB KICKER!", "" if not was_enabled else " (already had)")
		
		ServerPowerUpScript.PowerUpType.POWER_GLOVE:
			var was_enabled = has_power_glove
			has_power_glove = true
			print("[Player] ", username, " collected POWER GLOVE!", "" if not was_enabled else " (already had)")
		
		ServerPowerUpScript.PowerUpType.LINE_BOMB:
			var was_enabled = has_line_bomb
			has_line_bomb = true
			print("[Player] ", username, " collected LINE BOMB!", "" if not was_enabled else " (already had)")
		
		# === SPECIAL ITEMS ===
		ServerPowerUpScript.PowerUpType.FULL_FIRE:
			bomb_range = Constants.FIRE_MAX_FULL  # Set to max (16)
			print("[Player] ", username, " collected FULL FIRE! Range -> ", bomb_range)
		
		ServerPowerUpScript.PowerUpType.HEART:
			# Heart gives extra survivability - for now just log it
			# In a lives-based mode this would add a life
			print("[Player] ", username, " collected HEART! (extra life in lives mode)")
		
		ServerPowerUpScript.PowerUpType.GETA:
			# Negative item: reduce speed
			var old_val = skate_count
			skate_count = maxi(skate_count - 1, 0)
			speed_multiplier = GameConfig.get_skate_speed_multiplier(skate_count)
			print("[Player] ", username, " collected GETA (slow shoes)! ", old_val, " -> ", skate_count, " skates")
		
		# === BOMB TYPE CHANGERS ===
		ServerPowerUpScript.PowerUpType.REMOTE_BOMB:
			var old_type = bomb_type
			bomb_type = BOMB_TYPE_REMOTE
			print("[Player] ", username, " collected REMOTE BOMB! Bomb type: ", old_type, " -> ", bomb_type)
		
		ServerPowerUpScript.PowerUpType.POWER_BOMB, ServerPowerUpScript.PowerUpType.PIERCE_BOMB:
			var old_type = bomb_type
			bomb_type = BOMB_TYPE_POWER
			print("[Player] ", username, " collected POWER BOMB! Bomb type: ", old_type, " -> ", bomb_type)
		
		ServerPowerUpScript.PowerUpType.RUBBER_BOMB:
			var old_type = bomb_type
			bomb_type = BOMB_TYPE_RUBBER
			print("[Player] ", username, " collected RUBBER BOMB! Bomb type: ", old_type, " -> ", bomb_type)
		
		# === NEGATIVE ITEMS ===
		ServerPowerUpScript.PowerUpType.SKULL, ServerPowerUpScript.PowerUpType.VIRUS:
			# Apply random virus effect (Saturn Bomberman spec)
			var virus_options = [
				VirusType.SPEEDSTER,
				VirusType.SLOWPOKE,
				VirusType.DIARRHOEA,
				VirusType.CONSTIPATION,
				VirusType.SMALL_FLAME,
				VirusType.UNSTOPPABLE,
				VirusType.REVERSE,
				VirusType.HASTY_FUSE,
				VirusType.LEISURELY_FUSE,
			]
			var random_virus = virus_options[randi() % virus_options.size()]
			apply_virus(random_virus)
			print("[Player] ", username, " collected SKULL! Infected with: ", VirusType.keys()[random_virus])
		
		_:
			print("[Player] ", username, " collected unknown powerup type: ", type)

func get_state_minimal() -> Dictionary:
	# Minimal movement state - sent every tick for interpolation
	# Includes data that changes frequently (position, velocity)
	# Also includes game-critical stats for HUD display
	# Optimized for packet size - uses short keys and packed formats
	
	# Pack boolean flags into single integer to save bytes
	# Bit layout: [0]=kicker, [1]=glove, [2]=line_bomb, [3]=carrying, [4]=picking_up
	var flags = 0
	if has_bomb_kicker: flags |= 1
	if has_power_glove: flags |= 2
	if has_line_bomb: flags |= 4
	if is_carrying_bomb(): flags |= 8
	if is_picking_up_bomb: flags |= 16
	
	# Use single-char facing: U/D/L/R instead of UP/DOWN/LEFT/RIGHT
	var facing_char = "D"  # default down
	var f = _vector_to_facing(last_move_direction)
	if f == "UP": facing_char = "U"
	elif f == "DOWN": facing_char = "D"
	elif f == "LEFT": facing_char = "L"
	elif f == "RIGHT": facing_char = "R"
	
	# Dead players only need minimal state (position for death animation, dead flag)
	if is_dead:
		return {
			"p": [int(position.x), int(position.y)],
			"d": true,
		}
	
	# Pack stats into 2 integers for ultra-compact transmission:
	# s1: (max_bombs<<12) | (bomb_range<<8) | (bombs_placed<<4) | skate_count
	# s2: (bomb_type<<16) | (active_virus<<8) | flags
	var s1 = (max_bombs << 12) | (bomb_range << 8) | (bombs_placed << 4) | skate_count
	var s2 = (bomb_type << 16) | (active_virus << 8) | flags
	
	var state = {
		"p": [int(position.x), int(position.y)],  # position as array
		"f": facing_char,  # facing: U/D/L/R
		# Note: omit "d" for alive players - absence means alive (saves bytes)
		# Stats packed into 2 integers
		"s": [s1, s2],
	}
	# Only send velocity if non-zero (most players are stationary most of the time)
	if velocity.x != 0 or velocity.y != 0:
		state["v"] = [int(velocity.x), int(velocity.y)]
	# Only include optional fields if needed (to save bytes)
	if carried_bomb != null and is_instance_valid(carried_bomb):
		state["c"] = carried_bomb.bomb_id  # carried bomb id
	if active_virus != VirusType.NONE:
		state["ve"] = int(virus_end_time)  # virus end time
	if is_picking_up_bomb:
		state["pad"] = [int(pickup_animation_direction.x), int(pickup_animation_direction.y)]
	return state

func get_state() -> Dictionary:
	# Full state for network sync - sent on initial sync and when stats change
	var state = {
		"player_id": player_id,
		"username": username,
		"is_bot": is_bot,
		"position": {"x": position.x, "y": position.y},
		"velocity": {"x": velocity.x, "y": velocity.y},
		"facing": _vector_to_facing(last_move_direction),
		"is_dead": is_dead,
		"is_spectator": is_spectator,
		"bombs_placed": bombs_placed,
		"max_bombs": max_bombs,
		"bomb_range": bomb_range,
		"skate_count": skate_count,
		"speed_multiplier": speed_multiplier,
		"has_bomb_kicker": has_bomb_kicker,
		"has_power_glove": has_power_glove,
		"has_line_bomb": has_line_bomb,
		"bomb_type": bomb_type,
		"active_virus": active_virus,
		"virus_end_time": virus_end_time,
		"is_carrying_bomb": is_carrying_bomb(),
		"carried_bomb_id": carried_bomb.bomb_id if is_carrying_bomb() else "",
	}
	# Only include optional data if non-default
	if is_picking_up_bomb:
		state["is_picking_up_bomb"] = true
		state["pickup_animation_direction"] = {"x": pickup_animation_direction.x, "y": pickup_animation_direction.y}
	if bot_personality != "":
		state["bot_personality"] = bot_personality
	return state

func set_bot_metadata(personality: String) -> void:
	is_bot = true
	bot_personality = personality

func is_ai_bot() -> bool:
	return is_bot

# Debug line setup functions removed - now using scene nodes from ServerPlayer.tscn

@rpc("authority", "call_remote", "unreliable")
func client_update_debug_path(points: PackedVector2Array):
	if not debug_path_line:
		return
	
	var local_points = PackedVector2Array()
	for p in points:
		local_points.append(to_local(p))
	debug_path_line.points = local_points

@rpc("authority", "call_remote", "unreliable")
func client_update_debug_target_line(points: PackedVector2Array):
	if not debug_target_line:
		return

	var local_points = PackedVector2Array()
	for p in points:
		local_points.append(to_local(p))
	debug_target_line.points = local_points

func set_debug_path(points: PackedVector2Array):
	# Update locally (server view)
	if not debug_path_line:
		return
	
	var local_points = PackedVector2Array()
	for p in points:
		local_points.append(to_local(p))
	debug_path_line.points = local_points
	
	# Send to clients (skip for bots - they don't exist on client)
	if not is_bot:
		client_update_debug_path.rpc(points)

func set_debug_target_line(points: PackedVector2Array):
	if not debug_target_line:
		return

	debug_target_active = points.size() >= 2
	if debug_target_active:
		debug_target_center = points[points.size() - 1]
	else:
		debug_target_center = Vector2.ZERO

	var local_points = PackedVector2Array()
	for p in points:
		local_points.append(to_local(p))
	debug_target_line.points = local_points

	# Send to clients (skip for bots - they don't exist on client)
	if not is_bot:
		client_update_debug_target_line.rpc(points)
