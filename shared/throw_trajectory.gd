extends RefCounted

## The authority and public bot preview share the same deterministic waypoint
## rule. This preserves the current two-tile throw, twenty-step bounce limit,
## edge ordering and legacy fallback; complete=false is a policy refusal.
const THROW_RANGE := 2
const MAX_BOUNCES := 20

static func plan(start: Vector2i, direction: Vector2, dimensions: Vector2i,
		tile_size: float, collides: Callable) -> Dictionary:
	var waypoints: Array[Vector2] = []
	if dimensions.x <= 0 or dimensions.y <= 0 or tile_size <= 0.0 or not collides.is_valid():
		return {"waypoints": waypoints, "complete": false}
	var step := Vector2i.ZERO
	if absf(direction.x) > absf(direction.y): step.x = int(signf(direction.x))
	else: step.y = int(signf(direction.y))
	if step == Vector2i.ZERO: step = Vector2i.DOWN
	var landing := start + step * THROW_RANGE
	var remaining := MAX_BOUNCES
	var complete := false
	while remaining > 0:
		var wrapped := wrap_cell(landing, dimensions)
		var point := center(wrapped, tile_size)
		if collides.call(wrapped):
			var next := landing + step
			if crosses_boundary(landing, next, dimensions):
				_append_edges(waypoints, landing, next, dimensions, tile_size)
				landing = next + step
			else:
				waypoints.append(point)
				landing += step
		else:
			waypoints.append(point)
			complete = true
			break
		remaining -= 1
	if waypoints.is_empty():
		waypoints.append(center(wrap_cell(start + step * THROW_RANGE, dimensions), tile_size))
	for point in waypoints:
		var cell := Vector2i(floori(point.x / tile_size), floori(point.y / tile_size))
		if not Rect2i(Vector2i.ZERO, dimensions).has_point(cell): complete = false
	return {"waypoints": waypoints, "complete": complete}

static func center(cell: Vector2i, tile_size: float) -> Vector2:
	return Vector2(cell) * tile_size + Vector2.ONE * tile_size * 0.5

static func wrap_cell(cell: Vector2i, dimensions: Vector2i) -> Vector2i:
	# Preserve the authority's existing negative-coordinate behavior. A preview
	# flags an invalid resulting cell instead of silently changing game physics.
	var result := cell
	if result.x < 0: result.x = dimensions.x + result.x % dimensions.x
	elif result.x >= dimensions.x: result.x %= dimensions.x
	if result.y < 0: result.y = dimensions.y + result.y % dimensions.y
	elif result.y >= dimensions.y: result.y %= dimensions.y
	return result

static func crosses_boundary(from: Vector2i, to: Vector2i, dimensions: Vector2i) -> bool:
	return from.x >= 0 and from.x < dimensions.x and (to.x < 0 or to.x >= dimensions.x) \
		or from.y >= 0 and from.y < dimensions.y and (to.y < 0 or to.y >= dimensions.y)

static func _append_edges(points: Array[Vector2], from: Vector2i, to: Vector2i,
		dimensions: Vector2i, tile_size: float) -> void:
	var exit: Vector2i
	var entry: Vector2i
	if to.x < 0:
		exit = Vector2i(0, from.y); entry = Vector2i(dimensions.x - 1, from.y)
	elif to.x >= dimensions.x:
		exit = Vector2i(dimensions.x - 1, from.y); entry = Vector2i(0, from.y)
	elif to.y < 0:
		exit = Vector2i(from.x, 0); entry = Vector2i(from.x, dimensions.y - 1)
	elif to.y >= dimensions.y:
		exit = Vector2i(from.x, dimensions.y - 1); entry = Vector2i(from.x, 0)
	else: return
	points.append(center(exit, tile_size))
	points.append(center(entry, tile_size))

static func describe_flight(position: Vector2, arc_start: Vector2, throw_start: Vector2,
		throw_target: Vector2, arc_target: Vector2, progress: float, waypoint_index: int,
		waypoints: Array[Vector2], dimensions: Vector2i, tile_size: float,
		duration: float, frame_sec: float) -> Dictionary:
	var remaining: Array = []
	for index in range(waypoint_index, waypoints.size()):
		remaining.append([waypoints[index].x, waypoints[index].y])
	var first_sec := maxf(0.0, 1.0 - progress) * duration
	var minimum_sec := first_sec
	var maximum_sec := first_sec + maxi(remaining.size() - 1, 0) * duration + (remaining.size() + 1) * frame_sec
	var diagonal := Vector2(dimensions).length() * tile_size
	var trajectory := {Vector2i(floori(position.x / tile_size), floori(position.y / tile_size)): true}
	# Carried bombs can still have an overhead position at release. Native
	# flight immediately uses the ground arc, rather than interpolating from
	# that visual carry offset to its endpoint.
	var previous := arc_start.lerp(arc_target, clampf(progress, 0.0, 1.0))
	var complete := remaining.size() > 0 and remaining.size() <= 64
	for index in range(remaining.size()):
		var point := Vector2(float(remaining[index][0]), float(remaining[index][1]))
		# The first arc is always interpolated by native physics. Teleport
		# detection is performed only when entering a later arc segment.
		var wraps := waypoint_index + index > 0 and previous.distance_to(point) > diagonal * 0.5
		if index > 0 and not wraps: minimum_sec += duration
		if wraps:
			for edge in [previous, point]:
				trajectory[Vector2i(floori(edge.x / tile_size), floori(edge.y / tile_size))] = true
		else:
			var samples := maxi(1, ceili(maxf(absf(point.x - previous.x), absf(point.y - previous.y)) / tile_size * 2.0))
			if trajectory.size() + samples > 1024:
				complete = false
				break
			for sample in range(samples + 1):
				var probe: Vector2 = previous.lerp(point, float(sample) / samples)
				trajectory[Vector2i(floori(probe.x / tile_size), floori(probe.y / tile_size))] = true
		previous = point
	var landing := {}
	var last_start := arc_start if waypoints.size() < 2 else waypoints[-2]
	var fraction := maxf(0.0, 1.0 - frame_sec / duration)
	var near_end: Vector2 = last_start.lerp(throw_target, fraction)
	if waypoints.size() > 1 and last_start.distance_to(throw_target) > diagonal * 0.5:
		near_end = last_start
	var landing_samples := maxi(1, ceili(maxf(absf(throw_target.x - near_end.x), absf(throw_target.y - near_end.y)) / tile_size * 2.0))
	if landing_samples > 1024:
		complete = false
		landing_samples = 1
	for sample in range(landing_samples + 1):
		var probe: Vector2 = near_end.lerp(throw_target, float(sample) / landing_samples)
		landing[Vector2i(floori(probe.x / tile_size), floori(probe.y / tile_size))] = true
	var trajectory_cells: Array = []
	var landing_cells: Array = []
	for cell in trajectory: trajectory_cells.append([cell.x, cell.y])
	for cell in landing: landing_cells.append([cell.x, cell.y])
	return {"complete": complete, "throw_start": [throw_start.x, throw_start.y],
		"throw_target": [throw_target.x, throw_target.y], "arc_target": [arc_target.x, arc_target.y],
		"progress": progress, "waypoint_index": waypoint_index, "remaining_waypoints": remaining,
		"minimum_remaining_msec": minimum_sec * 1000.0, "maximum_remaining_msec": maximum_sec * 1000.0,
		"trajectory_cells": trajectory_cells, "landing_cells": landing_cells}
