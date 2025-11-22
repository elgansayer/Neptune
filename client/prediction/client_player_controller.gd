extends Node
class_name ClientPlayerController

# Client-Side Prediction & Server Reconciliation
# Implements lag mitigation for smooth, responsive player movement

const Constants = preload("res://shared/constants.gd")

# Input history for reconciliation
var input_history := []  # Array of {sequence: int, input: Dictionary, timestamp: float}
var next_input_sequence := 0

# Predicted state
var predicted_position := Vector2.ZERO
var predicted_velocity := Vector2.ZERO
var predicted_last_move_direction := Vector2.ZERO

# Saturn physics state (matches server_player.gd)
var predicted_speed_level := 0  # Discrete speed level (0-7)
var predicted_speed_multiplier := 1.0  # Calculated from speed_level
var predicted_current_speed_magnitude := 0.0  # Accumulated speed for momentum
var predicted_is_input_active := false  # Track input state for instant stop

# Server state (for reconciliation)
var server_position := Vector2.ZERO
var server_velocity := Vector2.ZERO
var last_server_sequence := -1

# Configuration
const INPUT_HISTORY_SIZE = 60  # Keep 1 second of inputs at 60 FPS
const RECONCILIATION_THRESHOLD = 10.0  # Pixels - only log if difference is significant
const PREDICTION_ENABLED = false  # DISABLED - too complex to match server's corner sliding
const DEBUG_RECONCILIATION = false  # Disabled - we know the issue now
const MIN_CORRECTION_INTERVAL = 0.5  # Only correct every 500ms (very infrequent)
const PREDICTION_WEIGHT = 0.99  # Trust prediction 99% - almost pure client-side
const MIN_ERROR_TO_CORRECT = 20.0  # Only correct errors larger than 20 pixels (major desync only)

var last_reconciliation_time := 0.0

func _ready():
	pass

func predict_movement(input_dir: Vector2, delta: float, _game_map: Array) -> Dictionary:
	"""
	Client-side prediction of player movement
	Returns: {position: Vector2, velocity: Vector2, last_move_direction: Vector2}
	"""
	if not PREDICTION_ENABLED:
		return {
			"position": predicted_position,
			"velocity": predicted_velocity,
			"last_move_direction": predicted_last_move_direction
		}
	
	# Store input in history (for future input replay if needed)
	var input_record = {
		"sequence": next_input_sequence,
		"input": {"x": input_dir.x, "y": input_dir.y},
		"timestamp": Time.get_ticks_msec() / 1000.0
	}
	input_history.append(input_record)
	next_input_sequence += 1
	
	# Trim old inputs
	if input_history.size() > INPUT_HISTORY_SIZE:
		input_history.pop_front()
	
	# Update speed multiplier from discrete level (Saturn formula)
	predicted_speed_multiplier = 1.0 + (predicted_speed_level * GameConfig.SPEED_LEVEL_INCREMENT)
	
	# Saturn stopping behavior: instant velocity drop on input release
	if input_dir.length() < Constants.INPUT_DEADZONE:
		predicted_is_input_active = false
		# Instant stop (Saturn behavior - no grid snap on stop)
		predicted_velocity = Vector2.ZERO
		predicted_current_speed_magnitude = 0.0
		
		# Apply stop movement
		predicted_position += predicted_velocity * delta
		
		return {
			"position": predicted_position,
			"velocity": predicted_velocity,
			"last_move_direction": predicted_last_move_direction
		}
	
	predicted_is_input_active = true
	
	# Match server speed calculation with Saturn physics
	var normalized_input = input_dir.normalized()
	var target_speed = GameConfig.BASE_SPEED * Constants.RUN_MULTIPLIER * predicted_speed_multiplier
	
	# Saturn momentum preservation: maintain speed magnitude during direction changes
	predicted_current_speed_magnitude = lerp(predicted_current_speed_magnitude, target_speed, GameConfig.ACCELERATION_RATE * delta)
	
	# Apply accumulated speed to current direction
	var target_velocity = normalized_input * predicted_current_speed_magnitude
	
	# Set velocity (already smoothed by acceleration)
	predicted_velocity = target_velocity
	
	# Match server's grid snapping logic EXACTLY (Saturn continuous alignment)
	var tile_center = get_current_tile_center()
	var offset_from_center = tile_center - predicted_position
	
	# When moving horizontally, snap vertically
	if abs(normalized_input.x) > 0.5:
		if abs(offset_from_center.y) > GameConfig.SNAP_THRESHOLD:
			var correction_y = sign(offset_from_center.y) * GameConfig.SNAP_TO_CENTER_SPEED
			predicted_velocity.y += correction_y
	
	# When moving vertically, snap horizontally
	if abs(normalized_input.y) > 0.5:
		if abs(offset_from_center.x) > GameConfig.SNAP_THRESHOLD:
			var correction_x = sign(offset_from_center.x) * GameConfig.SNAP_TO_CENTER_SPEED
			predicted_velocity.x += correction_x
	
	predicted_last_move_direction = normalized_input
	
	# Apply movement
	predicted_position += predicted_velocity * delta
	
	return {
		"position": predicted_position,
		"velocity": predicted_velocity,
		"last_move_direction": predicted_last_move_direction
	}

func get_current_tile_center() -> Vector2:
	"""Get the center position of the tile the player is currently on"""
	var tile_x = floor(predicted_position.x / GameConfig.TILE_SIZE)
	var tile_y = floor(predicted_position.y / GameConfig.TILE_SIZE)
	return Vector2(
		tile_x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
		tile_y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
	)

func reconcile_with_server(server_state: Dictionary):
	"""
	Server Reconciliation: Correct prediction errors
	When server state arrives, check if our prediction was wrong and correct it
	"""
	if not PREDICTION_ENABLED:
		# Without prediction, just use server state directly
		predicted_position = Vector2(server_state.position.x, server_state.position.y)
		predicted_velocity = Vector2(server_state.velocity.x, server_state.velocity.y)
		
		# Sync Saturn physics state from server
		if server_state.has("speed_level"):
			predicted_speed_level = server_state.speed_level
			predicted_speed_multiplier = server_state.speed_multiplier
		
		if DEBUG_RECONCILIATION:
			print("[No Prediction] Server pos: ", predicted_position)
		return
	
	var server_pos = Vector2(server_state.position.x, server_state.position.y)
	var server_vel = Vector2(server_state.velocity.x, server_state.velocity.y)
	var position_error = predicted_position.distance_to(server_pos)
	
	var current_time = Time.get_ticks_msec() / 1000.0
	var time_since_last = current_time - last_reconciliation_time
	
	if DEBUG_RECONCILIATION:
		print("[Reconcile] Error: %.2f px, Time since last: %.3f s" % [position_error, time_since_last])
	
	# Ignore small errors completely - they're likely due to timing differences
	if position_error < MIN_ERROR_TO_CORRECT:
		if DEBUG_RECONCILIATION:
			print("  -> Ignoring (below threshold)")
		return
	
	# Throttle corrections - don't correct too frequently
	if time_since_last < MIN_CORRECTION_INTERVAL:
		if DEBUG_RECONCILIATION:
			print("  -> Throttled (too soon)")
		return
	
	# Only correct significant errors
	var correction_strength = 0.0
	
	if position_error > 50.0:
		# Major desync - snap to server
		correction_strength = 0.8
		if DEBUG_RECONCILIATION:
			print("  -> MAJOR DESYNC - correcting 80%")
	elif position_error > 20.0:
		# Moderate error - gentle correction
		correction_strength = 0.3
		if DEBUG_RECONCILIATION:
			print("  -> Moderate error - correcting 30%")
	else:
		# Small error - very gentle
		correction_strength = 0.15
		if DEBUG_RECONCILIATION:
			print("  -> Small error - correcting 15%")
	
	# Apply correction
	predicted_position = predicted_position.lerp(server_pos, correction_strength)
	predicted_velocity = predicted_velocity.lerp(server_vel, correction_strength * 0.5)
	
	last_reconciliation_time = current_time

func reset_prediction(initial_position: Vector2):
	"""Reset prediction state (e.g., when spawning)"""
	predicted_position = initial_position
	predicted_velocity = Vector2.ZERO
	predicted_last_move_direction = Vector2.ZERO
	input_history.clear()
	next_input_sequence = 0
