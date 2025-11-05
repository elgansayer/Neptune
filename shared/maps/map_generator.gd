extends Node
class_name MapGenerator

# Dynamic Map Generation for Bomberman
# Generates procedural maps with various algorithms and layouts

const Constants = preload("res://shared/constants.gd")

enum TileType {
	EMPTY = 0,
	WALL = 1,
	DESTRUCTIBLE = 2,
	SPAWN_SAFE = 3  # Temporary marker for spawn zones
}

enum MapStyle {
	CLASSIC,      # Traditional grid pattern with random blocks
	ARENA,        # Open center, walls around edges
	MAZE,         # Dense maze-like structure
	CHAOS,        # Completely random placement
	WIDE,         # Large open areas for 9+ players
	SYMMETRIC     # Mirror symmetric for competitive play
}

# Map configuration
class MapConfig:
	var width: int = 15
	var height: int = 13
	var style: MapStyle = MapStyle.CLASSIC
	var destructible_density: float = 0.6  # 0.0 to 1.0
	var power_up_chance: float = 0.3  # Chance for power-up in destroyed block
	var spawn_points: Array = []  # Vector2 array
	var seed_value: int = -1  # -1 = random seed
	
	func _init(w: int = 15, h: int = 13):
		width = w
		height = h

static func generate_map(config: MapConfig) -> Dictionary:
	"""
	Generate a complete map with tiles, spawn points, and metadata
	Returns: {
		grid: Array (2D), 
		spawn_points: Array of Vector2,
		width: int,
		height: int,
		style: String,
		power_up_locations: Dictionary  # tile_key -> power_up_type
	}
	"""
	# Set random seed if specified
	if config.seed_value >= 0:
		seed(config.seed_value)
	
	var map_data = {
		"grid": [],
		"spawn_points": [],
		"width": config.width,
		"height": config.height,
		"style": MapStyle.keys()[config.style],
		"power_up_locations": {}
	}
	
	# Generate base layout
	match config.style:
		MapStyle.CLASSIC:
			map_data.grid = _generate_classic(config)
		MapStyle.ARENA:
			map_data.grid = _generate_arena(config)
		MapStyle.MAZE:
			map_data.grid = _generate_maze(config)
		MapStyle.CHAOS:
			map_data.grid = _generate_chaos(config)
		MapStyle.WIDE:
			map_data.grid = _generate_wide(config)
		MapStyle.SYMMETRIC:
			map_data.grid = _generate_symmetric(config)
	
	# Generate spawn points if not specified
	if config.spawn_points.is_empty():
		map_data.spawn_points = _generate_spawn_points(map_data.grid, config)
	else:
		map_data.spawn_points = config.spawn_points
	
	# Clear spawn zones (mark safe areas around spawns)
	_clear_spawn_zones(map_data.grid, map_data.spawn_points)
	
	return map_data

static func _generate_classic(config: MapConfig) -> Array:
	"""Traditional Bomberman grid pattern"""
	var grid = []
	grid.resize(config.height)
	
	for y in range(config.height):
		grid[y] = []
		grid[y].resize(config.width)
		
		for x in range(config.width):
			# Border walls
			if x == 0 or x == config.width - 1 or y == 0 or y == config.height - 1:
				grid[y][x] = TileType.WALL
			# Grid pattern walls (every other tile)
			elif x % 2 == 0 and y % 2 == 0:
				grid[y][x] = TileType.WALL
			# Empty or destructible
			else:
				if randf() < config.destructible_density:
					grid[y][x] = TileType.DESTRUCTIBLE
				else:
					grid[y][x] = TileType.EMPTY
	
	return grid

static func _generate_arena(config: MapConfig) -> Array:
	"""Open center with walls and blocks around edges"""
	var grid = []
	grid.resize(config.height)
	
	var center_x = config.width / 2.0
	var center_y = config.height / 2.0
	var open_radius = min(config.width, config.height) / 3.0
	
	for y in range(config.height):
		grid[y] = []
		grid[y].resize(config.width)
		
		for x in range(config.width):
			var dist_from_center = sqrt(pow(x - center_x, 2) + pow(y - center_y, 2))
			
			# Border walls
			if x == 0 or x == config.width - 1 or y == 0 or y == config.height - 1:
				grid[y][x] = TileType.WALL
			# Grid pattern walls only in outer areas
			elif x % 2 == 0 and y % 2 == 0 and dist_from_center > open_radius:
				grid[y][x] = TileType.WALL
			# Keep center open
			elif dist_from_center < open_radius:
				grid[y][x] = TileType.EMPTY
			# Outer areas have destructible blocks
			else:
				if randf() < config.destructible_density * 0.8:  # Less dense in arena
					grid[y][x] = TileType.DESTRUCTIBLE
				else:
					grid[y][x] = TileType.EMPTY
	
	return grid

static func _generate_maze(config: MapConfig) -> Array:
	"""Dense maze-like structure with winding paths"""
	var grid = []
	grid.resize(config.height)
	
	# Initialize with walls
	for y in range(config.height):
		grid[y] = []
		grid[y].resize(config.width)
		for x in range(config.width):
			grid[y][x] = TileType.WALL if (x % 2 == 0 or y % 2 == 0) else TileType.EMPTY
	
	# Carve paths using randomized Prim's algorithm
	var walls = []
	var start = Vector2i(1, 1)
	grid[start.y][start.x] = TileType.EMPTY
	
	# Add neighboring walls
	for dir in [Vector2i(0, 2), Vector2i(2, 0), Vector2i(0, -2), Vector2i(-2, 0)]:
		var next = start + dir
		if _is_in_bounds(next, config) and grid[next.y][next.x] == TileType.WALL:
			walls.append(next)
	
	while not walls.is_empty():
		var current = walls[randi() % walls.size()]
		walls.erase(current)
		
		if not _is_in_bounds(current, config):
			continue
		
		# Check if we can carve through this wall
		var neighbors = _get_carved_neighbors(current, grid, config)
		if neighbors.size() == 1:
			# Carve the wall and the cell between
			grid[current.y][current.x] = TileType.EMPTY
			var between = (current + neighbors[0]) / 2
			grid[between.y][between.x] = TileType.EMPTY
			
			# Add new walls
			for dir in [Vector2i(0, 2), Vector2i(2, 0), Vector2i(0, -2), Vector2i(-2, 0)]:
				var next = current + dir
				if _is_in_bounds(next, config) and grid[next.y][next.x] == TileType.WALL:
					if next not in walls:
						walls.append(next)
	
	# Add destructible blocks in some corridors
	for y in range(1, config.height - 1):
		for x in range(1, config.width - 1):
			if grid[y][x] == TileType.EMPTY and randf() < config.destructible_density * 0.4:
				grid[y][x] = TileType.DESTRUCTIBLE
	
	# Ensure borders are walls
	for x in range(config.width):
		grid[0][x] = TileType.WALL
		grid[config.height - 1][x] = TileType.WALL
	for y in range(config.height):
		grid[y][0] = TileType.WALL
		grid[y][config.width - 1] = TileType.WALL
	
	return grid

static func _generate_chaos(config: MapConfig) -> Array:
	"""Completely random placement - chaotic gameplay"""
	var grid = []
	grid.resize(config.height)
	
	for y in range(config.height):
		grid[y] = []
		grid[y].resize(config.width)
		
		for x in range(config.width):
			# Border walls
			if x == 0 or x == config.width - 1 or y == 0 or y == config.height - 1:
				grid[y][x] = TileType.WALL
			else:
				var rand = randf()
				if rand < 0.15:  # 15% solid walls
					grid[y][x] = TileType.WALL
				elif rand < 0.15 + config.destructible_density * 0.6:
					grid[y][x] = TileType.DESTRUCTIBLE
				else:
					grid[y][x] = TileType.EMPTY
	
	return grid

static func _generate_wide(config: MapConfig) -> Array:
	"""Large open areas for 9+ players"""
	var grid = []
	grid.resize(config.height)
	
	for y in range(config.height):
		grid[y] = []
		grid[y].resize(config.width)
		
		for x in range(config.width):
			# Border walls
			if x == 0 or x == config.width - 1 or y == 0 or y == config.height - 1:
				grid[y][x] = TileType.WALL
			# Sparse grid pattern (every 3rd tile)
			elif x % 3 == 0 and y % 3 == 0:
				grid[y][x] = TileType.WALL
			# Very sparse destructible blocks
			elif randf() < config.destructible_density * 0.4:
				grid[y][x] = TileType.DESTRUCTIBLE
			else:
				grid[y][x] = TileType.EMPTY
	
	return grid

static func _generate_symmetric(config: MapConfig) -> Array:
	"""Mirror symmetric for competitive play"""
	var grid = []
	grid.resize(config.height)
	
	# Generate one quadrant
	var half_w = int(config.width / 2.0)
	var half_h = int(config.height / 2.0)
	
	for y in range(config.height):
		grid[y] = []
		grid[y].resize(config.width)
		
		for x in range(config.width):
			# Only generate top-left quadrant
			if x <= half_w and y <= half_h:
				if x == 0 or y == 0:
					grid[y][x] = TileType.WALL
				elif x % 2 == 0 and y % 2 == 0:
					grid[y][x] = TileType.WALL
				elif randf() < config.destructible_density:
					grid[y][x] = TileType.DESTRUCTIBLE
				else:
					grid[y][x] = TileType.EMPTY
	
	# Mirror to all quadrants
	for y in range(config.height):
		for x in range(config.width):
			if x > half_w:
				grid[y][x] = grid[y][config.width - 1 - x]
			if y > half_h:
				grid[y][x] = grid[config.height - 1 - y][x]
	
	return grid

static func _generate_spawn_points(grid: Array, _config: MapConfig) -> Array:
	"""Generate optimal spawn points for players"""
	var spawns = []
	var height = grid.size()
	var width = grid[0].size()
	
	# Common spawn locations (corners and mid-edges)
	var potential_spawns = [
		Vector2(1, 1),                          # Top-left
		Vector2(width - 2, 1),                  # Top-right
		Vector2(1, height - 2),                 # Bottom-left
		Vector2(width - 2, height - 2),         # Bottom-right
		Vector2(int(width / 2.0), 1),                  # Top-center
		Vector2(int(width / 2.0), height - 2),         # Bottom-center
		Vector2(1, int(height / 2.0)),                 # Left-center
		Vector2(width - 2, int(height / 2.0)),         # Right-center
		Vector2(int(width / 4.0), int(height / 4.0)),         # Quarter positions
		Vector2(int(3 * width / 4.0), int(height / 4.0)),
		Vector2(int(width / 4.0), int(3 * height / 4.0)),
		Vector2(int(3 * width / 4.0), int(3 * height / 4.0))
	]
	
	# Filter and convert to world positions
	for spawn in potential_spawns:
		var tile_x = int(spawn.x)
		var tile_y = int(spawn.y)
		
		# Ensure spawn is on empty tile
		if tile_y < height and tile_x < width:
			if grid[tile_y][tile_x] == TileType.EMPTY or grid[tile_y][tile_x] == TileType.SPAWN_SAFE:
				# Convert to world position (center of tile)
				var world_pos = Vector2(
					tile_x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
					tile_y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
				)
				spawns.append(world_pos)
	
	return spawns

static func _clear_spawn_zones(grid: Array, spawn_points: Array):
	"""Clear area around spawn points to ensure players can move"""
	var height = grid.size()
	var width = grid[0].size()
	
	for spawn_pos in spawn_points:
		# Convert world position to tile
		var tile_x = int(spawn_pos.x / GameConfig.TILE_SIZE)
		var tile_y = int(spawn_pos.y / GameConfig.TILE_SIZE)
		
		# Clear 5x5 area around spawn (much clearer spawn zones)
		for dy in range(-2, 3):  # -2 to +2 = 5 tiles
			for dx in range(-2, 3):
				var check_x = tile_x + dx
				var check_y = tile_y + dy
				
				if check_y >= 0 and check_y < height and check_x >= 0 and check_x < width:
					# Don't remove permanent walls (grid pattern at even positions)
					if grid[check_y][check_x] == TileType.DESTRUCTIBLE:
						grid[check_y][check_x] = TileType.EMPTY

static func _is_in_bounds(pos: Vector2i, config: MapConfig) -> bool:
	return pos.x > 0 and pos.x < config.width - 1 and pos.y > 0 and pos.y < config.height - 1

static func _get_carved_neighbors(pos: Vector2i, grid: Array, config: MapConfig) -> Array:
	"""Get neighboring cells that have been carved (are empty)"""
	var neighbors = []
	for dir in [Vector2i(0, 2), Vector2i(2, 0), Vector2i(0, -2), Vector2i(-2, 0)]:
		var next = pos + dir
		if _is_in_bounds(next, config) and grid[next.y][next.x] == TileType.EMPTY:
			neighbors.append(next)
	return neighbors

# Utility function to export map to JSON
static func export_to_json(map_data: Dictionary) -> String:
	return JSON.stringify(map_data, "  ")

# Utility function to get a random map style
static func get_random_style() -> MapStyle:
	var styles = [MapStyle.CLASSIC, MapStyle.ARENA, MapStyle.MAZE, MapStyle.CHAOS, MapStyle.WIDE]
	return styles[randi() % styles.size()]
