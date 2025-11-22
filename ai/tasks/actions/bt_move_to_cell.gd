@tool
extends BTAction
class_name BTMoveToCell

## Moves the entity toward a target cell using pathfinding
## Calculates path once and follows waypoints, recalculating if stuck or target changes

@export var cell_var: StringName = &"target_cell" ## Blackboard variable containing target Vector2i
@export var reach_threshold: float = 0.1 ## Distance to consider "reached" (in tiles). 0.1 ~= 1.6px
@export var recalc_distance: int = 3 ## Manhattan distance to trigger path recalculation
@export var clear_on_success: bool = true ## Clear target_cell when reached
@export var avoid_threats: bool = false ## Whether to avoid threatened tiles during pathfinding
@export var debug_logging: bool = true

# State tracking between ticks
var _cached_path: Array[Vector2i] = []
var _cached_target: Vector2i = Vector2i(-999, -999)
var _current_waypoint_index: int = 0
var _stuck_counter: int = 0
var _last_position: Vector2 = Vector2.ZERO

func _generate_name() -> String:
	print("[BTMoveToCell] _generate_name() called - cell_var property is: '", cell_var, "'")
	return "MoveToCell(%s)" % cell_var

func _tick(_delta: float) -> int:
	print("[BTMoveToCell] _tick called") # UNCOMMENTED for debugging
	var player = blackboard.get_var("player")
	var target_cell = blackboard.get_var(cell_var)
	var grid_sampler = blackboard.get_var("grid_sampler")
	
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
	
	# Check if we've reached the destination tile AND are reasonably centered
	# This is critical for safety - bot must be centered to avoid blast from adjacent tiles
	if current_tile == target_cell:
		var target_center = grid_sampler.tile_to_world_center(target_cell)
		var distance_to_center = player.position.distance_to(target_center)
		
		# Allow 3 pixels tolerance (tiles are 16px, so this is well within safe zone)
		# This is lenient enough to avoid getting stuck, but strict enough for safety
		if distance_to_center < 3.0:
			# Reached destination tile AND reasonably centered
			print("[BTMoveToCell] Reached target cell: %s (centered within %.1fpx)" % [target_cell, distance_to_center])
			if clear_on_success:
				blackboard.set_var(cell_var, null)
			
			# Stop movement
			player.set_input(0.0, 0.0)
			if player.has_method("set_debug_path"):
				player.set_debug_path(PackedVector2Array())
			_reset_state()
			
			return SUCCESS
		# else: In target tile but not centered yet, keep moving
	
	# Detect if stuck (not moving)
	if player.position.distance_to(_last_position) < 0.5:
		_stuck_counter += 1
		if _stuck_counter > 30: # ~0.5 seconds at 60fps
			print("[BTMoveToCell] Bot stuck at %s (last=%s dist=%.2f), recalculating path" % [player.position, _last_position, player.position.distance_to(_last_position)])
			
			# Debug collisions
			for i in range(player.get_slide_collision_count()):
				var collision = player.get_slide_collision(i)
				if collision:
					print("  COLLISION: ", collision.get_collider().name, " at ", collision.get_position())
			
			# Debug map around

			if grid_sampler:
				current_tile = player.get_tile_position()
				print("  Map around ", current_tile, ":")
				for dy in range(-1, 2):
					var line = ""
					for dx in range(-1, 2):
						var t = current_tile + Vector2i(dx, dy)
						var walkable = grid_sampler.is_tile_walkable(t)
						line += "[%d,%d:%s] " % [t.x, t.y, "." if walkable else "X"]
					print("    " + line)

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
			_cached_path = grid_sampler.find_path(current_tile, target_cell, 40, player, avoid_threats)
		
		if _cached_path.is_empty():
			print("[BTMoveToCell] FAILURE: No path found from ", current_tile, " to ", target_cell)
			if player.has_method("set_debug_path"):
				player.set_debug_path(PackedVector2Array())
			_reset_state()
			return FAILURE
		
		print("[BTMoveToCell] Calculated path with %d waypoints to %s: %s" % [_cached_path.size(), target_cell, _cached_path])
		_draw_debug_path(player, grid_sampler)
	
	
	# Get current waypoint and its CENTER position
	if _current_waypoint_index >= _cached_path.size():
		# Reached end of path but not at target? Recalculate
		_cached_path = []
		return RUNNING
	
	var waypoint = _cached_path[_current_waypoint_index]
	var waypoint_center = grid_sampler.tile_to_world_center(waypoint)
	
	# Check PHYSICAL distance to waypoint center
	var dist_to_waypoint_center = player.position.distance_to(waypoint_center)
	var center_threshold = 3.0 # pixels - reasonable centering (tiles are 16px)
	
	# Log every 60 frames
	if Engine.get_physics_frames() % 60 == 0:
		var current_tile_pos = player.get_tile_position()
		print("[BTMoveToCell] Target=%s Current=%s Waypoint=%s Dist=%.1f Index=%d/%d" % [
			target_cell, current_tile_pos, waypoint, dist_to_waypoint_center, _current_waypoint_index, _cached_path.size()
		])
	
	# If we've reached the waypoint center (within tolerance), advance to next waypoint
	if dist_to_waypoint_center < center_threshold:
		_current_waypoint_index += 1
		if _current_waypoint_index >= _cached_path.size():
			# Path complete, let success check at top handle it
			return RUNNING
		# Get next waypoint
		waypoint = _cached_path[_current_waypoint_index]
		waypoint_center = grid_sampler.tile_to_world_center(waypoint)
	
	# Move toward waypoint CENTER (not grid position!)
	# Use ONE AXIS AT A TIME for strict orthogonal movement
	var offset = waypoint_center - player.position
	var direction: Vector2
	
	if abs(offset.x) > abs(offset.y):
		# Move horizontally first
		direction = Vector2(sign(offset.x), 0.0)
	else:
		# Move vertically
		direction = Vector2(0.0, sign(offset.y))
	
	player.set_input(direction.x, direction.y)
	
	return RUNNING

func _reset_state() -> void:
	_cached_path = []
	_cached_target = Vector2i(-999, -999)
	_current_waypoint_index = 0
	_stuck_counter = 0

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
		print("[DEBUG DRAW] Sending points: ", points)
		player.set_debug_path(points)
