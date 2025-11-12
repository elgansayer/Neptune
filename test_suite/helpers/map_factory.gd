extends Node

# Provides deterministic map dictionaries matching GameInstance expectations.
# grid: 2D Array[int] (0 empty,1 wall,2 soft), spawn_points: Array[Vector2]

func small_open() -> Dictionary:
	# 9x7 map with border walls (1) and empty interior.
	var w = 9
	var h = 7
	var grid = []
	for y in range(h):
		var row = []
		for x in range(w):
			if x == 0 or y == 0 or x == w-1 or y == h-1:
				row.append(1)  # border wall
			else:
				row.append(0)
		grid.append(row)
	return {
		"grid": grid,
		"spawn_points": [Vector2(1*64+32,3*64+32), Vector2(7*64+32,3*64+32)],
		"name": "small_open",
		"soft_slots": [],
		"metadata": {}
	}

func soft_block_line() -> Dictionary:
	# 7x5 with one soft block east of start at (3,2)
	var w = 7
	var h = 5
	var grid = []
	for y in range(h):
		var row = []
		for x in range(w):
			if x == 0 or y == 0 or x == w-1 or y == h-1:
				row.append(1)
			else:
				row.append(0)
		grid.append(row)
	# place soft block at (3,2)
	grid[2][3] = 2
	return {
		"grid": grid,
		"spawn_points": [Vector2(2*64+32,2*64+32)],
		"name": "soft_block_line",
		"soft_slots": [Vector2i(3,2)],
		"metadata": {}
	}

func trap_corridor() -> Dictionary:
	# Narrow horizontal corridor 11x5, walls top/bottom, interior open.
	var w = 11
	var h = 5
	var grid = []
	for y in range(h):
		var row = []
		for x in range(w):
			if y == 0 or y == h-1:
				row.append(1)
			else:
				row.append(0)
		grid.append(row)
	return {
		"grid": grid,
		"spawn_points": [Vector2(2*64+32,2*64+32), Vector2(8*64+32,2*64+32)],
		"name": "trap_corridor",
		"soft_slots": [],
		"metadata": {}
	}
