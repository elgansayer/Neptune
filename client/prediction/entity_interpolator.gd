extends Node
class_name EntityInterpolator

# Entity Interpolation for Remote Players
# Smoothly interpolates between server snapshots for remote entities
# Adds interpolation delay to ensure smooth movement despite network jitter

# State buffer for interpolation
var state_buffer := []  # Array of {position: Vector2, velocity: Vector2, timestamp: float}
const BUFFER_SIZE = 5  # Keep recent states (reduced to avoid over-smoothing)
const INTERPOLATION_DELAY = 0.08  # 80ms delay for smooth interpolation (reduced from 100ms)

# Current interpolated state
var interpolated_position := Vector2.ZERO
var interpolated_velocity := Vector2.ZERO
var last_update_time := 0.0

func add_server_state(position: Vector2, velocity: Vector2, timestamp: float = 0.0):
	"""Add a new server state to the buffer"""
	if timestamp == 0.0:
		timestamp = Time.get_ticks_msec() / 1000.0
	
	# Avoid adding duplicate or out-of-order states
	if state_buffer.size() > 0:
		var last_state = state_buffer[state_buffer.size() - 1]
		if timestamp <= last_state.timestamp:
			return  # Ignore old or duplicate states
		
		# If position hasn't changed significantly, don't add redundant state
		if last_state.position.distance_to(position) < 0.1:
			return
	
	state_buffer.append({
		"position": position,
		"velocity": velocity,
		"timestamp": timestamp
	})
	
	last_update_time = timestamp
	
	# Keep buffer size manageable
	while state_buffer.size() > BUFFER_SIZE:
		state_buffer.pop_front()

func get_interpolated_position(current_time: float = 0.0) -> Vector2:
	"""
	Get interpolated position based on buffered states
	Renders entities slightly in the past for smooth movement
	"""
	if current_time == 0.0:
		current_time = Time.get_ticks_msec() / 1000.0
	
	if state_buffer.size() == 0:
		return interpolated_position
	
	if state_buffer.size() == 1:
		# Only one state, use it directly
		interpolated_position = state_buffer[0].position
		return interpolated_position
	
	# Render time is slightly in the past
	var render_time = current_time - INTERPOLATION_DELAY
	
	# Find the two states to interpolate between
	var from_state = null
	var to_state = null
	
	for i in range(state_buffer.size() - 1):
		if state_buffer[i].timestamp <= render_time and state_buffer[i + 1].timestamp >= render_time:
			from_state = state_buffer[i]
			to_state = state_buffer[i + 1]
			break
	
	# If render time is ahead of all states, use the latest state
	if from_state == null or to_state == null:
		var latest_state = state_buffer[state_buffer.size() - 1]
		
		# Check if we're too far ahead - extrapolate if needed
		var time_since_last_update = current_time - last_update_time
		if time_since_last_update < 0.2:  # Only extrapolate for short gaps
			# Extrapolate using velocity
			var extrapolated = latest_state.position + latest_state.velocity * (render_time - latest_state.timestamp)
			interpolated_position = interpolated_position.lerp(extrapolated, 0.3)
		else:
			# Too old, just use latest position
			interpolated_position = latest_state.position
		
		return interpolated_position
	
	# Interpolate between states
	var time_diff = to_state.timestamp - from_state.timestamp
	if time_diff > 0:
		var t = (render_time - from_state.timestamp) / time_diff
		t = clamp(t, 0.0, 1.0)
		interpolated_position = from_state.position.lerp(to_state.position, t)
	else:
		interpolated_position = to_state.position
	
	return interpolated_position

func extrapolate_position(delta: float) -> Vector2:
	"""
	Dead Reckoning / Extrapolation
	Predict future position when no server update arrives
	"""
	if state_buffer.size() == 0:
		return interpolated_position
	
	var latest_state = state_buffer[state_buffer.size() - 1]
	
	# Extrapolate using last known velocity
	var extrapolated = latest_state.position + latest_state.velocity * delta
	
	return extrapolated

func reset():
	"""Clear interpolation buffer"""
	state_buffer.clear()
	interpolated_position = Vector2.ZERO
	interpolated_velocity = Vector2.ZERO
