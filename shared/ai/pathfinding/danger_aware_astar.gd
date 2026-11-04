extends AStarGrid2D
class_name DangerAwareAStar

## Bounded safe-interval A*: a state is a tile and a safe time interval.
## Earliest-deadline callers retain conservative semantics. Interval callers
## can wait for observed flames to expire without discretising simulation time.
## Source and destination must be clear throughout each edge traversal.
const EPSILON_MSEC := 0.001
var threat_matrix_ref: Dictionary = {}
var hazard_intervals_ref: Dictionary = {}
var use_hazard_intervals := false
var allow_wait := true
var use_start_world_position := false
var start_world_position := Vector2.ZERO
var path_start_time_msec := 0.0
var path_start_pos := Vector2i.ZERO # Legacy utility caller compatibility.
var bot_speed_msec_per_tile := 200.0
var safety_buffer_msec := 100.0
var max_expansions := 2048
var max_generated_states := 8192
var horizon_msec := 12000.0
var last_route: Dictionary = {}

func _key(cell: Vector2i) -> String:
	return "%d,%d" % [cell.x, cell.y]

func _deadline(cell: Vector2i) -> float:
	return float(threat_matrix_ref.get(_key(cell), threat_matrix_ref.get(cell, INF)))

func _safe_intervals(cell: Vector2i) -> Array[Vector2]:
	var windows: Array = hazard_intervals_ref.get(_key(cell), hazard_intervals_ref.get(cell, [])) if use_hazard_intervals else []
	if windows.size() > 64:
		return []
	if not use_hazard_intervals and _deadline(cell) < INF:
		windows = [Vector2(_deadline(cell), INF)]
	var unsafe: Array[Vector2] = []
	for window in windows:
		if window is Vector2:
			unsafe.append(window)
		elif window is Array and window.size() == 2:
			unsafe.append(Vector2(float(window[0]), float(window[1])))
		else:
			return []
	unsafe.sort_custom(func(a, b): return a.x < b.x or a.x == b.x and a.y < b.y)
	var safe: Array[Vector2] = []
	var start := -INF
	for window in unsafe:
		if is_nan(window.x) or is_nan(window.y) or window.y < window.x:
			return []
		var end := window.x - safety_buffer_msec
		if start < end:
			safe.append(Vector2(start, end))
		start = maxf(start, window.y + safety_buffer_msec + EPSILON_MSEC)
		if start == INF:
			break
	if start < INF:
		safe.append(Vector2(start, INF))
	return safe

func _earlier(a: Dictionary, b: Dictionary) -> bool:
	return a.priority < b.priority or a.priority == b.priority and a.serial < b.serial

func _push(heap: Array, entry: Dictionary) -> void:
	heap.append(entry)
	var index := heap.size() - 1
	while index > 0:
		var parent: int = (index - 1) / 2
		if not _earlier(heap[index], heap[parent]):
			break
		var swap = heap[parent]
		heap[parent] = heap[index]
		heap[index] = swap
		index = parent

func _pop(heap: Array) -> Dictionary:
	var first: Dictionary = heap[0]
	var tail = heap.pop_back()
	if heap.is_empty():
		return first
	heap[0] = tail
	var index := 0
	while index * 2 + 1 < heap.size():
		var child := index * 2 + 1
		if child + 1 < heap.size() and _earlier(heap[child + 1], heap[child]):
			child += 1
		if not _earlier(heap[child], heap[index]):
			break
		var swap = heap[index]
		heap[index] = heap[child]
		heap[child] = swap
		index = child
	return first

func get_timed_route(from_id: Vector2i, to_id: Vector2i, max_steps: int = 30, goal_cells: Dictionary = {}, require_unbounded_goal: bool = false) -> Dictionary:
	last_route = {"status": "invalid", "cells": [], "arrivals": [], "departures": [], "expanded": 0}
	if max_steps < 0 or max_expansions <= 0 or max_generated_states <= 0 or not is_finite(path_start_time_msec) or not is_finite(bot_speed_msec_per_tile) or bot_speed_msec_per_tile <= 0.0 or not is_finite(safety_buffer_msec) or safety_buffer_msec < 0.0 or not is_finite(horizon_msec) or horizon_msec <= 0.0:
		return last_route.duplicate(true)
	if not region.has_point(from_id) or not region.has_point(to_id) or is_point_solid(from_id) or is_point_solid(to_id):
		return last_route.duplicate(true)
	var cache := {from_id: _safe_intervals(from_id)}
	var start_interval := -1
	for index in range(cache[from_id].size()):
		var interval: Vector2 = cache[from_id][index]
		if path_start_time_msec >= interval.x and path_start_time_msec < interval.y:
			start_interval = index
			break
	last_route.status = "unreachable"
	if start_interval < 0:
		return last_route.duplicate(true)
	var states: Array[Dictionary] = [{"cell": from_id, "interval": start_interval, "arrival": path_start_time_msec, "depth": 0, "parent": -1, "departure": path_start_time_msec}]
	var labels := {"%s:%d" % [_key(from_id), start_interval]: [0]}
	var heap: Array = []
	var serial := 0
	_push(heap, {"state": 0, "priority": path_start_time_msec, "serial": serial})
	while not heap.is_empty():
		if last_route.expanded >= max_expansions:
			last_route.status = "exhausted"
			return last_route.duplicate(true)
		var entry := _pop(heap)
		var state: Dictionary = states[entry.state]
		var cell: Vector2i = state.cell
		last_route.expanded += 1
		var reached_goal: bool = cell == to_id if goal_cells.is_empty() else goal_cells.has(cell)
		if reached_goal and (not require_unbounded_goal or cache[cell][state.interval].y == INF):
			var cells: Array[Vector2i] = []
			var arrivals: Array[float] = []
			var departures: Array[float] = []
			var cursor: int = entry.state
			while cursor >= 0:
				cells.append(states[cursor].cell)
				arrivals.append(states[cursor].arrival)
				departures.append(states[cursor].departure)
				cursor = states[cursor].parent
			cells.reverse()
			arrivals.reverse()
			departures.reverse()
			last_route.merge({"status": "found", "cells": cells, "arrivals": arrivals, "departures": departures}, true)
			return last_route.duplicate(true)
		if state.depth >= max_steps:
			continue
		var source_interval: Vector2 = cache[cell][state.interval]
		for direction: Vector2i in [Vector2i.RIGHT, Vector2i.LEFT, Vector2i.UP, Vector2i.DOWN]:
			var next := cell + direction
			if not region.has_point(next) or is_point_solid(next):
				continue
			if not cache.has(next):
				cache[next] = _safe_intervals(next)
			for interval_index in range(cache[next].size()):
				var target_interval: Vector2 = cache[next][interval_index]
				# Occupy both cells throughout the crossing to cover the actor's
				# footprint, source departure and destination entry clearance.
				var departure := maxf(state.arrival, target_interval.x)
				if not allow_wait and departure > state.arrival + EPSILON_MSEC:
					continue
				var crossing_msec := bot_speed_msec_per_tile
				if state.depth == 0 and use_start_world_position:
					var offset: Vector2 = get_point_position(next) + cell_size * 0.5 - start_world_position
					crossing_msec *= (absf(offset.x) + absf(offset.y)) / maxf(cell_size.x, 1.0)
				var arrival := departure + crossing_msec
				if arrival >= source_interval.y or arrival >= target_interval.y or arrival > path_start_time_msec + horizon_msec:
					continue
				var label := "%s:%d" % [_key(next), interval_index]
				var dominated := false
				for prior_index in labels.get(label, []):
					var prior: Dictionary = states[prior_index]
					if prior.arrival <= arrival and prior.depth <= state.depth + 1:
						dominated = true
						break
				if dominated:
					continue
				if states.size() >= max_generated_states:
					last_route.status = "exhausted"
					return last_route.duplicate(true)
				if not labels.has(label):
					labels[label] = []
				labels[label].append(states.size())
				states.append({"cell": next, "interval": interval_index, "arrival": arrival, "depth": state.depth + 1, "parent": entry.state, "departure": departure})
				serial += 1
				var distance := absi(next.x - to_id.x) + absi(next.y - to_id.y) if goal_cells.is_empty() else 0
				_push(heap, {"state": states.size() - 1, "priority": arrival + distance * bot_speed_msec_per_tile, "serial": serial})
	return last_route.duplicate(true)

func get_timed_id_path(from_id: Vector2i, to_id: Vector2i, max_steps: int = 30) -> Array[Vector2i]:
	var route := get_timed_route(from_id, to_id, max_steps)
	var path: Array[Vector2i] = []
	path.assign(route.cells)
	return path

func get_timed_point_path(from_id: Vector2i, to_id: Vector2i, max_steps: int = 30) -> PackedVector2Array:
	var points := PackedVector2Array()
	for cell in get_timed_id_path(from_id, to_id, max_steps):
		points.append(get_point_position(cell))
	return points
