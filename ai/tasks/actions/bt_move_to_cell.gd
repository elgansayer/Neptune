@tool
extends BTAction
class_name BTMoveToCell

## Moves the entity toward a target cell using pathfinding
## Calculates path once and follows waypoints, recalculating if stuck or target changes

@export var cell_var: StringName = &"target_cell"  ## Blackboard variable containing target Vector2i
@export var reach_threshold: float = 0.5  ## Distance to consider "reached" (in tiles)
@export var recalc_distance: int = 3  ## Manhattan distance to trigger path recalculation
@export var clear_on_success: bool = true  ## Clear target_cell when reached
@export var debug_logging: bool = false

# State tracking between ticks
var _cached_path: Array[Vector2i] = []
var _cached_target: Vector2i = Vector2i(-999, -999)
var _current_waypoint_index: int = 0
var _stuck_counter: int = 0
var _last_position: Vector2 = Vector2.ZERO

func _generate_name() -> String:
	return "MoveToCell(%s)" % cell_var

func _tick(delta: float) -> int:
	var player = blackboard.get_var("player")
	var target_cell = blackboard.get_var(cell_var)
	var grid_sampler = blackboard.get_var("grid_sampler")
	
	if not player:
		push_warning("[BTMoveToCell] Missing player in blackboard")
		return FAILURE
	
	if not grid_sampler:
		push_warning("[BTMoveToCell] Missing grid_sampler in blackboard")
		return FAILURE
	
	# If no target cell, fail silently (expected when no powerups/objectives available)
	if target_cell == null:
		_reset_state()
		return FAILURE
	
	# Convert to Vector2i if needed
	if not target_cell is Vector2i:
		if target_cell is Vector2:
			target_cell = Vector2i(int(target_cell.x), int(target_cell.y))
		else:
			push_warning("[BTMoveToCell] Invalid target cell type: %s" % target_cell)
			_reset_state()
			return FAILURE
	
	var current_tile = grid_sampler.world_to_tile(player.position)
	
	# Check if we've reached the destination
	var target_pos = grid_sampler.tile_to_world_center(target_cell)
	var distance = player.position.distance_to(target_pos)
	var threshold_pixels = GameConfig.TILE_SIZE * reach_threshold
	
	if distance < threshold_pixels:
		# Reached destination
		print("[BTMoveToCell] Reached target cell: ", target_cell)
		if clear_on_success:
			blackboard.set_var(cell_var, null)
		
		# Stop movement
		player.set_input(0.0, 0.0)
		_reset_state()
		
		return SUCCESS
	
	# Detect if stuck (not moving)
	if player.position.distance_to(_last_position) < 0.5:
		_stuck_counter += 1
		if _stuck_counter > 30:  # ~0.5 seconds at 60fps
			print("[BTMoveToCell] Bot stuck, recalculating path")
			_cached_path = []
			_stuck_counter = 0
	else:
		_stuck_counter = 0
	_last_position = player.position
	
	# Recalculate path if target changed or no path exists
	if target_cell != _cached_target or _cached_path.is_empty():
		_cached_target = target_cell
		_current_waypoint_index = 0
		
		# Special case: If we are already in the target tile, just move to center
		if current_tile == target_cell:
			_cached_path = [target_cell]
		else:
			_cached_path = grid_sampler.find_path(current_tile, target_cell, 40, player)
		
		if _cached_path.is_empty():
			push_warning("[BTMoveToCell] No path found from %s to %s" % [current_tile, target_cell])
			player.set_input(0.0, 0.0)
			_reset_state()
			return FAILURE
		
		print("[BTMoveToCell] Calculated path with %d waypoints to %s" % [_cached_path.size(), target_cell])
	
	# Get current waypoint
	if _current_waypoint_index >= _cached_path.size():
		# Reached end of path but not at target? Recalculate
		_cached_path = []
		return RUNNING
	
	var waypoint = _cached_path[_current_waypoint_index]
	var waypoint_pos = grid_sampler.tile_to_world_center(waypoint)
	
	# Check if we need to advance to next waypoint
	var waypoint_distance = player.position.distance_to(waypoint_pos)
	if waypoint_distance < GameConfig.TILE_SIZE * 0.4:  # Within 40% of tile size
		_current_waypoint_index += 1
		if _current_waypoint_index >= _cached_path.size():
			# Reached final waypoint, target should be very close now
			waypoint_pos = target_pos
		else:
			waypoint = _cached_path[_current_waypoint_index]
			waypoint_pos = grid_sampler.tile_to_world_center(waypoint)
	
	# Check if we're too far off the path (collision pushed us away)
	var expected_tile = grid_sampler.world_to_tile(waypoint_pos)
	var tile_distance = grid_sampler.get_manhattan_distance(current_tile, expected_tile)
	if tile_distance > recalc_distance:
		print("[BTMoveToCell] Off path (distance: %d), recalculating" % tile_distance)
		_cached_path = []
		return RUNNING
	
	# Move toward current waypoint using grid-aligned movement
	# This prevents diagonal shortcuts through obstacles
	var delta_pos = waypoint_pos - player.position
	var direction: Vector2
	
	# Prioritize the axis with larger difference (move one axis at a time)
	if abs(delta_pos.x) > abs(delta_pos.y):
		# Move horizontally
		direction = Vector2(sign(delta_pos.x), 0.0)
	else:
		# Move vertically
		direction = Vector2(0.0, sign(delta_pos.y))
	
	player.set_input(direction.x, direction.y)
	
	return RUNNING

func _reset_state() -> void:
	_cached_path = []
	_cached_target = Vector2i(-999, -999)
	_current_waypoint_index = 0
	_stuck_counter = 0
