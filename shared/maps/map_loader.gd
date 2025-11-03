extends Node
class_name MapLoader

# Map Loader for Bomberman
# Loads maps from JSON files and validates them

const Constants = preload("res://shared/constants.gd")

enum TileType {
	EMPTY = 0,
	WALL = 1,
	DESTRUCTIBLE = 2
}

static func load_map_from_file(file_path: String) -> Dictionary:
	"""
	Load a map from a JSON file
	Returns: {
		grid: Array (2D),
		spawn_points: Array of Vector2,
		width: int,
		height: int,
		name: String,
		metadata: Dictionary
	}
	Or null if failed to load
	"""
	if not FileAccess.file_exists(file_path):
		push_error("Map file not found: " + file_path)
		return {}
	
	var file = FileAccess.open(file_path, FileAccess.READ)
	if file == null:
		push_error("Failed to open map file: " + file_path)
		return {}
	
	var json_text = file.get_as_text()
	file.close()
	
	var json = JSON.new()
	var error = json.parse(json_text)
	
	if error != OK:
		push_error("Failed to parse JSON in map file: " + file_path)
		return {}
	
	var data = json.data
	
	if not data is Dictionary:
		push_error("Invalid map file format: " + file_path)
		return {}
	
	# Parse and validate the map
	return parse_map_data(data, file_path.get_file().get_basename())

static func parse_map_data(data: Dictionary, map_name: String = "Unnamed") -> Dictionary:
	"""
	Parse and validate map data from dictionary
	"""
	var map_result = {
		"grid": [],
		"spawn_points": [],
		"width": 0,
		"height": 0,
		"name": map_name,
		"metadata": {}
	}
	
	# Extract grid
	if not data.has("grid"):
		push_error("Map missing 'grid' field")
		return {}
	
	var grid = data.grid
	if not grid is Array or grid.is_empty():
		push_error("Map grid is invalid or empty")
		return {}
	
	# Validate grid structure
	map_result.height = grid.size()
	map_result.width = grid[0].size() if grid.size() > 0 else 0
	
	# Ensure all rows have same width
	for row in grid:
		if not row is Array or row.size() != map_result.width:
			push_error("Map grid has inconsistent row widths")
			return {}
	
	map_result.grid = grid
	
	# Extract spawn points
	if data.has("spawn_points"):
		var spawns = data.spawn_points
		if spawns is Array:
			for spawn in spawns:
				if spawn is Dictionary and spawn.has("x") and spawn.has("y"):
					# Convert tile coordinates to world coordinates
					var world_pos = Vector2(
						spawn.x * Constants.TILE_SIZE + Constants.TILE_SIZE / 2.0,
						spawn.y * Constants.TILE_SIZE + Constants.TILE_SIZE / 2.0
					)
					map_result.spawn_points.append(world_pos)
				elif spawn is Array and spawn.size() >= 2:
					# Array format [x, y]
					var world_pos = Vector2(
						spawn[0] * Constants.TILE_SIZE + Constants.TILE_SIZE / 2.0,
						spawn[1] * Constants.TILE_SIZE + Constants.TILE_SIZE / 2.0
					)
					map_result.spawn_points.append(world_pos)
	
	# If no spawn points defined, generate default ones
	if map_result.spawn_points.is_empty():
		map_result.spawn_points = _generate_default_spawns(map_result.grid, map_result.width, map_result.height)
	
	# Extract metadata
	if data.has("name"):
		map_result.name = data.name
	if data.has("metadata"):
		map_result.metadata = data.metadata
	if data.has("author"):
		map_result.metadata["author"] = data.author
	if data.has("description"):
		map_result.metadata["description"] = data.description
	
	return map_result

static func _generate_default_spawns(grid: Array, width: int, height: int) -> Array:
	"""Generate default spawn points in corners"""
	var spawns = []
	
	# Corner positions
	var corners = [
		Vector2(1, 1),
		Vector2(width - 2, 1),
		Vector2(1, height - 2),
		Vector2(width - 2, height - 2)
	]
	
	for corner in corners:
		var tile_x = int(corner.x)
		var tile_y = int(corner.y)
		
		# Check if position is valid (empty or destructible, not wall)
		if tile_y < height and tile_x < width:
			if grid[tile_y][tile_x] != TileType.WALL:
				var world_pos = Vector2(
					tile_x * Constants.TILE_SIZE + Constants.TILE_SIZE / 2.0,
					tile_y * Constants.TILE_SIZE + Constants.TILE_SIZE / 2.0
				)
				spawns.append(world_pos)
	
	return spawns

static func save_map_to_file(map_data: Dictionary, file_path: String) -> bool:
	"""
	Save a map to a JSON file
	"""
	# Convert map_data to saveable format
	var save_data = {
		"name": map_data.get("name", "Unnamed Map"),
		"grid": map_data.grid,
		"spawn_points": [],
		"metadata": map_data.get("metadata", {})
	}
	
	# Convert spawn points from world coords to tile coords
	for spawn in map_data.spawn_points:
		save_data.spawn_points.append({
			"x": int(spawn.x / Constants.TILE_SIZE),
			"y": int(spawn.y / Constants.TILE_SIZE)
		})
	
	# Write to file
	var file = FileAccess.open(file_path, FileAccess.WRITE)
	if file == null:
		push_error("Failed to open file for writing: " + file_path)
		return false
	
	file.store_string(JSON.stringify(save_data, "  "))
	file.close()
	
	print("[MapLoader] Saved map to: ", file_path)
	return true

static func list_available_maps(directory: String = "res://res/maps/") -> Array:
	"""
	List all available map files in a directory
	Returns array of file paths
	"""
	var maps = []
	
	if not DirAccess.dir_exists_absolute(directory):
		push_warning("Map directory does not exist: " + directory)
		return maps
	
	var dir = DirAccess.open(directory)
	if dir == null:
		push_error("Failed to open directory: " + directory)
		return maps
	
	dir.list_dir_begin()
	var file_name = dir.get_next()
	
	while file_name != "":
		if not dir.current_is_dir() and file_name.ends_with(".json"):
			maps.append(directory + file_name)
		file_name = dir.get_next()
	
	dir.list_dir_end()
	
	return maps

static func get_map_preview(file_path: String) -> Dictionary:
	"""
	Load just the metadata of a map without loading the full grid
	Returns: {name: String, metadata: Dictionary, spawn_count: int}
	"""
	if not FileAccess.file_exists(file_path):
		return {}
	
	var file = FileAccess.open(file_path, FileAccess.READ)
	if file == null:
		return {}
	
	var json_text = file.get_as_text()
	file.close()
	
	var json = JSON.new()
	var error = json.parse(json_text)
	
	if error != OK:
		return {}
	
	var data = json.data
	if not data is Dictionary:
		return {}
	
	var preview = {
		"name": data.get("name", "Unnamed"),
		"metadata": data.get("metadata", {}),
		"spawn_count": 0,
		"size": Vector2i(0, 0)
	}
	
	if data.has("spawn_points") and data.spawn_points is Array:
		preview.spawn_count = data.spawn_points.size()
	
	if data.has("grid") and data.grid is Array and not data.grid.is_empty():
		preview.size.y = data.grid.size()
		preview.size.x = data.grid[0].size()
	
	return preview

static func validate_map(map_data: Dictionary) -> Dictionary:
	"""
	Validate a map and return warnings/errors
	Returns: {valid: bool, errors: Array[String], warnings: Array[String]}
	"""
	var result = {
		"valid": true,
		"errors": [],
		"warnings": []
	}
	
	# Check required fields
	if not map_data.has("grid") or map_data.grid.is_empty():
		result.errors.append("Map has no grid data")
		result.valid = false
		return result
	
	var grid = map_data.grid
	var height = grid.size()
	var width = grid[0].size()
	
	# Check minimum size
	if width < 7 or height < 7:
		result.warnings.append("Map is very small (minimum recommended: 7x7)")
	
	# Check spawn points
	if not map_data.has("spawn_points") or map_data.spawn_points.is_empty():
		result.errors.append("Map has no spawn points")
		result.valid = false
	elif map_data.spawn_points.size() < 2:
		result.warnings.append("Map has only " + str(map_data.spawn_points.size()) + " spawn point(s). Recommended: 4+")
	
	# Check for walls around borders
	var has_border = true
	for x in range(width):
		if grid[0][x] != TileType.WALL or grid[height - 1][x] != TileType.WALL:
			has_border = false
			break
	for y in range(height):
		if grid[y][0] != TileType.WALL or grid[y][width - 1] != TileType.WALL:
			has_border = false
			break
	
	if not has_border:
		result.warnings.append("Map doesn't have complete border walls")
	
	# Check for completely blocked areas (basic connectivity check)
	var empty_tiles = 0
	for row in grid:
		for tile in row:
			if tile == TileType.EMPTY:
				empty_tiles += 1
	
	if empty_tiles < width * height * 0.1:
		result.warnings.append("Map has very few empty tiles - gameplay may be too constrained")
	
	return result
