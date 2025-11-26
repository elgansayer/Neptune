@tool
extends BTAction
class_name BTMoveToCell

## Moves the entity toward a target cell using pathfinding
## Calculates path once and follows waypoints, recalculating if stuck or target changes
## Includes COMMITMENT logic to prevent jittering when target shifts slightly

@export var cell_var: StringName = &"target_cell" ## Blackboard variable containing target Vector2i
@export var reach_threshold: float = 0.1 ## Distance to consider "reached" (in tiles). 0.1 ~= 1.6px
@export var recalc_distance: int = 3 ## Manhattan distance to trigger path recalculation
@export var clear_on_success: bool = true ## Clear target_cell when reached
@export var avoid_threats: bool = false ## Whether to avoid threatened tiles during pathfinding
@export var debug_logging: bool = true

# State tracking between ticks
var _cached_path: Array[Vector2i] = []
var _cached_target: Vector2i = Vector2i(-999, -999)
var _committed_target: Vector2i = Vector2i(-999, -999) # Target we are committed to reaching
var _current_waypoint_index: int = 0
var _stuck_counter: int = 0
var _last_position: Vector2 = Vector2.ZERO
var _stuck_start_position: Vector2 = Vector2.ZERO  # Position when we started counting stuck
var _stuck_start_time: float = 0.0  # Real time (msec) when we started tracking stuck
var _completed_successfully: bool = false # Track if we finished via SUCCESS

# Stuck detection parameters
const STUCK_TIME_THRESHOLD_MS: float = 500.0  # 0.5 seconds of low movement
const STUCK_DISTANCE_THRESHOLD: float = 4.0  # Should move at least 4 pixels in that time (about quarter tile)
const MIN_FRAME_MOVEMENT: float = 0.1  # Below this, we consider frame as "stuck"

func _generate_name() -> String:
	# print("[BTMoveToCell] _generate_name() called - cell_var property is: '", cell_var, "'")
	return "MoveToCell(%s)" % cell_var

func _enter() -> void:
	# print("[BTMoveToCell:%s] _enter() CALLED - cell_var=%s" % [custom_name, cell_var])
	_completed_successfully = false

func _exit() -> void:
	var player = blackboard.get_var("player")
	if player:
		# Only reset input if we were INTERRUPTED (not if we completed successfully)
		# When we complete successfully, input was already reset in _tick()
		if not _completed_successfully:
			# CRITICAL FIX: Do NOT reset input here!
			# The behavior tree might be resetting/restarting this task rapidly (e.g. due to BTSelector re-evaluation).
			# If we reset input to (0,0), the bot will stutter and stop moving, leading to death.
			# Let the next task (or the restart of this task) handle input.
			# player.set_input(0.0, 0.0)
			if debug_logging:
				print("[BTMoveToCell] _exit() called - INTERRUPTED. _completed_successfully=", _completed_successfully)
		elif debug_logging:
			print("[BTMoveToCell] _exit() called - completed successfully, input already reset")
		
		if player.has_method("set_debug_path"):
			player.set_debug_path(PackedVector2Array())
		if player.has_method("set_debug_target_line"):
			player.set_debug_target_line(PackedVector2Array())
			
	_reset_state()
	_completed_successfully = false

func _tick(_delta: float) -> int:
	# print("[BTMoveToCell] _tick called") # UNCOMMENTED for debugging - DISABLED: too spammy
	var player = blackboard.get_var("player")
	
	# Early exit if player is dead
	if player and player.is_dead:
		player.set_input(0.0, 0.0)
		return FAILURE
	
	var target_cell = blackboard.get_var(cell_var, null)
	var grid_sampler = blackboard.get_var("grid_sampler")
	
	var in_danger = false
	if blackboard.has_var("in_danger"):
		in_danger = blackboard.get_var("in_danger")
	
	# Only log occasionally to reduce spam
	var should_log = debug_logging and (Engine.get_physics_frames() % 30 == 0)
	
	if should_log:
		print("[BTMoveToCell] _tick() called - cell_var='", cell_var, "' target_cell=", target_cell)
	
	if not player:
		push_warning("[BTMoveToCell] Missing player in blackboard")
		return FAILURE
	
	if not grid_sampler:
		push_warning("[BTMoveToCell] Missing grid_sampler in blackboard")
		return FAILURE
	
	# If no target cell, fail silently (expected when no powerups/objectives available)
	if target_cell == null:
		# print("[BTMoveToCell] FAILURE: target_cell is null") # Commented out to avoid spam if expected
		if player.has_method("set_debug_path"):
			player.set_debug_path(PackedVector2Array())
		if player.has_method("set_debug_target_line"):
			player.set_debug_target_line(PackedVector2Array())
		
		# CRITICAL: Stop moving if we have no target!
		player.set_input(0.0, 0.0)
		_reset_state()
		return FAILURE
	

	# Convert to Vector2i if needed
	if not target_cell is Vector2i:
		if target_cell is Vector2:
			target_cell = Vector2i(int(target_cell.x), int(target_cell.y))
		else:
			push_warning("[BTMoveToCell] Invalid target cell type: %s" % target_cell)
			player.set_input(0.0, 0.0)
			_reset_state()
			return FAILURE
	
	var current_tile = grid_sampler.world_to_tile(player.position)
	var target_center = grid_sampler.tile_to_world_center(target_cell)
	var offset_from_center = target_center - player.position
	var abs_offset_x = abs(offset_from_center.x)
	var abs_offset_y = abs(offset_from_center.y)
	var tile_half_extent = GameConfig.TILE_SIZE * 0.5
	var inside_target_tile = abs_offset_x <= tile_half_extent and abs_offset_y <= tile_half_extent
	if player.has_method("set_debug_target_line"):
		var target_line = PackedVector2Array()
		target_line.append(player.position)
		target_line.append(target_center)
		player.set_debug_target_line(target_line)
	
	# Check if we've reached the destination tile AND are reasonably centered
	# This is critical for safety - bot must be centered to avoid blast from adjacent tiles
	if inside_target_tile:
		# CRITICAL: Must be centered on BOTH axes, not just overall distance!
		# Check each axis independently to prevent stopping when only one axis is aligned
		var target_x_centered = abs_offset_x < 1.0
		var target_y_centered = abs_offset_y < 1.0
		var both_centered = target_x_centered and target_y_centered
		
		if both_centered:
			# Snap to exact center now that we've naturally moved there
			player.position = target_center
			# Reached destination tile AND fully centered on both axes
			print("[BTMoveToCell] ✓✓✓ SUCCESS: Reached target %s - Pos: (%.2f, %.2f), Center: (%.2f, %.2f), Offset: (%.2fpx, %.2fpx)" % [
				target_cell, player.position.x, player.position.y, target_center.x, target_center.y,
				abs(offset_from_center.x), abs(offset_from_center.y)
			])
			if clear_on_success:
				blackboard.set_var(cell_var, null)
			
			# Stop movement - CRITICAL: set input to zero!
			player.set_input(0.0, 0.0)
			# print("[BTMoveToCell] Input set to (0.0, 0.0) - Bot should stop moving")
			if player.has_method("set_debug_target_line"):
				player.set_debug_target_line(PackedVector2Array())
			
			if player.has_method("set_debug_path"):
				player.set_debug_path(PackedVector2Array())
			_reset_state()
			
			_completed_successfully = true
			return SUCCESS
		else:
			# In target tile but not fully centered yet - log this frequently!
			if Engine.get_physics_frames() % 10 == 0:
				print("[BTMoveToCell] In target tile %s but NOT fully centered: x=%.1fpx %s, y=%.1fpx %s | Pos: %s, Center: %s" % [
					target_cell,
					abs_offset_x, "✓" if target_x_centered else "✗",
					abs_offset_y, "✓" if target_y_centered else "✗",
					player.position, target_center
				])
			# CRITICAL: Set input toward center and return RUNNING to avoid waypoint logic interfering
			# CRITICAL: Set input toward center and return RUNNING to avoid waypoint logic interfering
			# Use proportional speed to avoid overshoot/oscillation
			var center_direction: Vector2 = Vector2.ZERO
			var speed_factor = 1.0
			
			if abs_offset_x > abs_offset_y:
				# Correct X
				center_direction.x = sign(offset_from_center.x)
				# Slow down if very close (within 2px)
				if abs_offset_x < 2.0:
					speed_factor = 0.5
			else:
				# Correct Y
				center_direction.y = sign(offset_from_center.y)
				if abs_offset_y < 2.0:
					speed_factor = 0.5
					
			player.set_input(center_direction.x * speed_factor, center_direction.y * speed_factor)
			return RUNNING
	
	# Detect if stuck using REAL TIME (immune to timescale changes)
	var current_time_ms = Time.get_ticks_msec()
	var frame_movement = player.position.distance_to(_last_position)
	
	if frame_movement < MIN_FRAME_MOVEMENT:  # Very little movement this frame
		if _stuck_counter == 0:
			_stuck_start_position = _last_position
			_stuck_start_time = current_time_ms
		_stuck_counter += 1
		
		# Check using REAL TIME elapsed
		var elapsed_ms = current_time_ms - _stuck_start_time
		var total_stuck_movement = player.position.distance_to(_stuck_start_position)
		
		# Scale threshold by timescale - at 0.1x speed, expect 0.1x distance
		var current_timescale = Engine.time_scale
		var scaled_threshold = STUCK_DISTANCE_THRESHOLD * current_timescale
		# Minimum threshold of 1 pixel to avoid triggering on tiny floating point differences
		scaled_threshold = max(scaled_threshold, 1.0)
		
		# Only trigger if we've been stuck for STUCK_TIME_THRESHOLD_MS and moved less than scaled threshold
		if elapsed_ms >= STUCK_TIME_THRESHOLD_MS and total_stuck_movement < scaled_threshold:
			print("[BTMoveToCell] frame=%d Bot stuck at %s (elapsed=%.0fms moved=%.2fpx thresh=%.2f) recalculating path" % [
				Engine.get_physics_frames(), player.position, elapsed_ms, total_stuck_movement, scaled_threshold])
			
			# Debug collisions
			for i in range(player.get_slide_collision_count()):
				var collision = player.get_slide_collision(i)
				if collision:
					print("  COLLISION: ", collision.get_collider().name, " at ", collision.get_position())
			
			# If we are stuck, penalize the target and fail
			if target_cell != null:
				_apply_stuck_penalty(target_cell)
				blackboard.set_var(cell_var, null)
			
			_cached_path = []
			_stuck_counter = 0
			_stuck_start_time = 0.0
			player.set_input(0.0, 0.0) # Stop trying to push wall
			_reset_state()
			return FAILURE
		# If we've been tracking stuck but ARE making progress, keep monitoring
	else:
		# Good movement this frame - reset stuck tracking
		_stuck_counter = 0
		_stuck_start_time = 0.0
	_last_position = player.position
	
	# Check if target is penalized
	if target_cell != null:
		# CRITICAL EXCEPTION: Never penalize the ESCAPE CELL!
		# If we are trying to escape, we must try even if we got stuck there before.
		# Dying to a bomb is worse than bumping into a wall.
		var is_escape = (cell_var == "escape_cell")
		
		if not is_escape:
			var stuck_targets = {}
			if blackboard.has_var("stuck_targets"):
				stuck_targets = blackboard.get_var("stuck_targets")
			
			var t_key = "%d,%d" % [target_cell.x, target_cell.y]
			if stuck_targets.has(t_key):
				if Time.get_ticks_msec() < stuck_targets[t_key]:
					print("[BTMoveToCell] ABORT: Target %s is currently penalized (stuck recently)" % target_cell)
					blackboard.set_var(cell_var, null)
					player.set_input(0.0, 0.0)
					_reset_state()
					return FAILURE
				else:
					stuck_targets.erase(t_key) # Expired
	
	# Recalculate path if target changed or no path exists
	# COMMITMENT LOGIC:
	# If we are already moving to a committed target, do NOT recalculate unless:
	# 1. The new target is SIGNIFICANTLY DIFFERENT (dist > 1)
	# 2. The path is blocked/invalid
	# 3. We are in danger (override commitment)
	
	var needs_recalc = false
	
	# Check if target changed significantly
	if target_cell != _cached_target:
		# If we have a committed target, check if we should abandon it
		if _committed_target != Vector2i(-999, -999):
			# If in danger, always allow switching (safety first)
			if in_danger:
				needs_recalc = true
				_committed_target = Vector2i(-999, -999) # Break commitment
				if should_log: print("[BTMoveToCell] BREAKING COMMITMENT due to DANGER")
			
			# If new target is the same as committed, keep going (don't recalc)
			elif target_cell == _committed_target:
				needs_recalc = false
			
			else:
				# New target is different. Is it close enough to ignore?
				var dist_change = abs(target_cell.x - _committed_target.x) + abs(target_cell.y - _committed_target.y)
				if dist_change <= 1:
					# Target shifted slightly (e.g. adjacent tile). Stick to original!
					# This prevents jitter when tactical assessment wobbles between two adjacent tiles
					needs_recalc = false
					if should_log: print("[BTMoveToCell] IGNORING minor target shift %s -> %s" % [_committed_target, target_cell])
				else:
					# Significant change, switch
					needs_recalc = true
					_committed_target = Vector2i(-999, -999)
		else:
			needs_recalc = true
			
	if _cached_path.is_empty():
		needs_recalc = true
		
	if needs_recalc:
		_cached_target = target_cell
		_committed_target = target_cell # Commit to this new target
		_current_waypoint_index = 0
		
		# Special case: If we are already inside the target tile bounds, just move to center
		if inside_target_tile:
			_cached_path = [target_cell]
		else:
			_cached_path = grid_sampler.find_path(current_tile, target_cell, 40, player, avoid_threats)
		
		if _cached_path.is_empty():
			print("[BTMoveToCell] FAILURE: No path found from ", current_tile, " to ", target_cell)
			_apply_stuck_penalty(target_cell) # Penalize this unreachable target
			if player.has_method("set_debug_path"):
				player.set_debug_path(PackedVector2Array())
			blackboard.set_var(cell_var, null) # Clear target so we don't retry immediately
			player.set_input(0.0, 0.0)
			_reset_state()
			return FAILURE
		
		print("[BTMoveToCell] Calculated path with %d waypoints to %s: %s" % [_cached_path.size(), target_cell, _cached_path])
		_draw_debug_path(player, grid_sampler)
	elif should_log:
		print("[BTMoveToCell] Maintaining commitment to %s (path len %d)" % [_committed_target, _cached_path.size()])
	
	
	# Get current waypoint and its CENTER position
	if _current_waypoint_index >= _cached_path.size():
		# Completed the path - should be in target tile now, let top centering logic handle it
		# Don't clear path yet, just continue to next frame where inside_target_tile will be true
		# Set input toward target center to keep moving
		var offset_to_target = target_center - player.position
		var final_direction: Vector2
		if abs(offset_to_target.x) > abs(offset_to_target.y):
			final_direction = Vector2(sign(offset_to_target.x), 0.0)
		else:
			final_direction = Vector2(0.0, sign(offset_to_target.y))
		player.set_input(final_direction.x, final_direction.y)
		return RUNNING
	
	var waypoint = _cached_path[_current_waypoint_index]
	var waypoint_center = grid_sampler.tile_to_world_center(waypoint)
	
	# Check PHYSICAL distance to waypoint center
	var dist_to_waypoint_center = player.position.distance_to(waypoint_center)
	var center_threshold = 1.0 # pixels - tight centering (adaptive to tile size, strict for precision)
	
	# Log every 60 frames
	if Engine.get_physics_frames() % 60 == 0:
		var current_tile_pos = player.get_tile_position()
		print("[BTMoveToCell] Target=%s Current=%s Waypoint=%s Dist=%.1f Index=%d/%d" % [
			target_cell, current_tile_pos, waypoint, dist_to_waypoint_center, _current_waypoint_index, _cached_path.size()
		])
	
	# ALWAYS calculate movement toward waypoint center FIRST
	# This ensures we keep moving even when about to advance waypoint
	var offset = waypoint_center - player.position
	var direction: Vector2
	
	# CRITICAL: Check if we're centered on BOTH axes individually
	# We must be within threshold on BOTH X and Y to consider the waypoint reached
	var x_centered = abs(offset.x) < center_threshold
	var y_centered = abs(offset.y) < center_threshold
	var both_axes_centered = x_centered and y_centered
	
	# Use ONE AXIS AT A TIME for strict orthogonal movement
	# Prioritize the axis that needs more correction
	if abs(offset.x) > abs(offset.y):
		# Move horizontally first
		direction = Vector2(sign(offset.x), 0.0)
	else:
		# Move vertically
		direction = Vector2(0.0, sign(offset.y))
	
	# Set movement input toward waypoint
	player.set_input(direction.x, direction.y)
	
	# AFTER setting input, check if we've reached the waypoint and should advance
	# CRITICAL: Only advance if BOTH X and Y axes are centered!
	# This ensures the bot fully centers on each tile before moving on
	if both_axes_centered:
		_current_waypoint_index += 1
		print("[BTMoveToCell] Advanced to waypoint %d/%d - FULLY CENTERED (x=%.1fpx, y=%.1fpx)" % [
			_current_waypoint_index, _cached_path.size(), abs(offset.x), abs(offset.y)
		])
	elif Engine.get_physics_frames() % 10 == 0:
		# Debug: Show which axis still needs centering (more frequent logging)
		var centering_status = "x_off=%.1fpx %s, y_off=%.1fpx %s" % [
			abs(offset.x), "✓" if x_centered else "✗",
			abs(offset.y), "✓" if y_centered else "✗"
		]
		print("[BTMoveToCell] Centering waypoint %d/%d: %s | Pos: %s, Target: %s" % [
			_current_waypoint_index, _cached_path.size(), centering_status, player.position, waypoint_center
		])
	
	return RUNNING

func _reset_state() -> void:
	_cached_path = []
	_cached_target = Vector2i(-999, -999)
	_committed_target = Vector2i(-999, -999)
	_current_waypoint_index = 0
	_stuck_counter = 0
	_stuck_start_position = Vector2.ZERO
	_stuck_start_time = 0.0

func _draw_debug_path(player, grid_sampler) -> void:
	"""Draw the planned path as a visual line"""
	if not is_instance_valid(player):
		return
	
	# Build points array from path - follow grid with 90-degree turns
	var points = PackedVector2Array()
	points.append(player.position) # Start from player
	
	var current_pos = player.position
	for tile in _cached_path:
		var target_pos = grid_sampler.tile_to_world_center(tile)
		
		# Add intermediate point if we need to turn (create L-shape instead of diagonal)
		var delta = target_pos - current_pos
		if abs(delta.x) > 1 and abs(delta.y) > 1:
			# Moving diagonally - add corner point
			# Move horizontally first, then vertically
			var corner = Vector2(target_pos.x, current_pos.y)
			points.append(corner)
			print("[DEBUG DRAW] Added corner at ", corner, " for delta ", delta)
		
		points.append(target_pos)
		current_pos = target_pos
	
	# Use player's method to update path (replicated to clients)
	if player.has_method("set_debug_path"):
		# print("[DEBUG DRAW] Sending points: ", points)
		player.set_debug_path(points)

func _apply_stuck_penalty(target: Vector2i) -> void:
	"""Apply a temporary penalty to this target so we don't immediately retry it"""
	if not blackboard.has_var("stuck_targets"):
		blackboard.set_var("stuck_targets", {})
	
	var stuck_targets = blackboard.get_var("stuck_targets")
	var current_time = Time.get_ticks_msec()
	
	# Clean up old entries first
	var keys_to_remove = []
	for k in stuck_targets:
		if current_time > stuck_targets[k]:
			keys_to_remove.append(k)
	for k in keys_to_remove:
		stuck_targets.erase(k)
	
	# Add new penalty (3 seconds)
	var key = "%d,%d" % [target.x, target.y]
	stuck_targets[key] = current_time + 3000
	print("[BTMoveToCell] 🚫 APPLIED STUCK PENALTY to %s (expires in 3s)" % target)
