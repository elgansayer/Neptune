extends RefCounted

## Earliest conservative deadlines for stationary normal blast geometry.
## Input is public bomb observations, never private sampled long-fuse values.
static func build(game: Node, sampler, now_msec: float, hypothetical: Dictionary = {}) -> Dictionary:
	var threats := {}
	if game == null or sampler == null:
		return threats
	for key in game.active_explosion_tiles:
		if game.active_explosion_tiles[key] >= now_msec:
			threats[key] = now_msec
	var observations: Array = []
	for bomb in game.bombs.values():
		if is_instance_valid(bomb) and not bomb.has_exploded:
			observations.append(bomb.get_forecast_observation())
	if not hypothetical.is_empty():
		observations.append(hypothetical)
	var deadlines: Array[float] = []
	var blasts: Array = []
	var at_cell := {}
	var queue: Array[int] = []
	for index in range(observations.size()):
		var observation: Dictionary = observations[index]
		var cell: Vector2i = observation.cell
		deadlines.append(now_msec + maxf(float(observation.fuse_lower_bound) - float(observation.elapsed), 0.0) * 1000.0)
		blasts.append(project(cell, observation.range, sampler))
		if not at_cell.has(cell):
			at_cell[cell] = []
		at_cell[cell].append(index)
		queue.append(index)
	var settled := {}
	while not queue.is_empty():
		# Reorder on changed deadlines, including a late bomb shortened by a chain.
		queue.sort_custom(func(a, b): return deadlines[a] < deadlines[b] or (deadlines[a] == deadlines[b] and a < b))
		var index: int = queue.pop_front()
		settled[index] = true
		var deadline: float = deadlines[index]
		for cell: Vector2i in blasts[index]:
			var key := "%d,%d" % [cell.x, cell.y]
			threats[key] = minf(float(threats.get(key, INF)), deadline)
			for other in at_cell.get(cell, []):
				if not settled.has(other):
					deadlines[other] = minf(deadlines[other], deadline)
	return threats

static func project(origin: Vector2i, radius: int, sampler) -> Array[Vector2i]:
	var cells: Array[Vector2i] = []
	if not sampler.is_in_bounds(origin):
		return cells
	cells.append(origin)
	for direction: Vector2i in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		for distance in range(1, radius + 1):
			var cell: Vector2i = origin + direction * distance
			if not sampler.is_in_bounds(cell):
				break
			var tile_type: int = sampler.get_tile_type(cell)
			if tile_type == 1 or tile_type == 3:
				break
			cells.append(cell)
			if tile_type == 2:
				break
	return cells
