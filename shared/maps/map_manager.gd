extends Node
class_name MapManager

# Central Map Management System
# Handles loading, generating, and managing game maps

const Constants = preload("res://shared/constants.gd")
const MapGenerator = preload("res://shared/maps/map_generator.gd")
const MapLoader = preload("res://shared/maps/map_loader.gd")

enum MapSource {
	FILE,       # Load from JSON file
	GENERATE,   # Procedurally generate
	CUSTOM      # Custom map data passed in
}

# Current loaded map data
var current_map: Dictionary = {}

func load_map(source: MapSource, param: Variant = null) -> Dictionary:
	"""
	Load a map from various sources
	
	Parameters:
	- source: MapSource enum (FILE, GENERATE, CUSTOM)
	- param: 
	  * For FILE: String file path (e.g., "res://res/maps/classic_arena.json")
	  * For GENERATE: MapGenerator.MapConfig or MapGenerator.MapStyle
	  * For CUSTOM: Dictionary with map data
	
	Returns: Map dictionary or empty dict on failure
	"""
	match source:
		MapSource.FILE:
			if param is String:
				current_map = MapLoader.load_map_from_file(param)
			else:
				push_error("[MapManager] FILE source requires String file path")
				return {}
		
		MapSource.GENERATE:
			if param is MapGenerator.MapConfig:
				current_map = MapGenerator.generate_map(param)
			elif param is int:  # MapStyle enum value
				var config = MapGenerator.MapConfig.new()
				config.style = param as MapGenerator.MapStyle
				current_map = MapGenerator.generate_map(config)
			else:
				# Generate default classic map
				var config = MapGenerator.MapConfig.new()
				current_map = MapGenerator.generate_map(config)
		
		MapSource.CUSTOM:
			if param is Dictionary:
				current_map = param
			else:
				push_error("[MapManager] CUSTOM source requires Dictionary")
				return {}
	
	if current_map.is_empty():
		push_error("[MapManager] Failed to load map")
		return {}
	
	print("[MapManager] Loaded map: ", current_map.get("name", "Unnamed"), 
		  " (", current_map.width, "x", current_map.height, ")")
	
	return current_map

func load_random_map_file() -> Dictionary:
	"""Load a random map from the maps directory"""
	var maps = MapLoader.list_available_maps()
	
	if maps.is_empty():
		push_warning("[MapManager] No map files found, generating procedural map")
		return load_map(MapSource.GENERATE, MapGenerator.MapStyle.CLASSIC)
	
	var random_map = maps[randi() % maps.size()]
	print("[MapManager] Loading random map: ", random_map)
	return load_map(MapSource.FILE, random_map)

func generate_procedural_map(style: MapGenerator.MapStyle = MapGenerator.MapStyle.CLASSIC, 
							  width: int = 15, height: int = 13) -> Dictionary:
	"""Generate a new procedural map with specified style"""
	var config = MapGenerator.MapConfig.new(width, height)
	config.style = style
	return load_map(MapSource.GENERATE, config)

func get_spawn_point(player_index: int) -> Vector2:
	"""Get spawn point for a specific player index"""
	if current_map.is_empty() or not current_map.has("spawn_points"):
		push_error("[MapManager] No map loaded or no spawn points available")
		return Vector2(64, 64)  # Default fallback
	
	var spawns = current_map.spawn_points
	if spawns.is_empty():
		push_error("[MapManager] Map has no spawn points")
		return Vector2(64, 64)
	
	# Cycle through available spawns
	var spawn_index = player_index % spawns.size()
	return spawns[spawn_index]

func get_all_spawn_points() -> Array:
	"""Get all available spawn points"""
	if current_map.is_empty() or not current_map.has("spawn_points"):
		return []
	return current_map.spawn_points

func get_map_grid() -> Array:
	"""Get the current map's tile grid"""
	if current_map.is_empty() or not current_map.has("grid"):
		return []
	return current_map.grid

func get_map_size() -> Vector2i:
	"""Get the current map's dimensions"""
	if current_map.is_empty():
		return Vector2i(0, 0)
	return Vector2i(current_map.get("width", 0), current_map.get("height", 0))

func get_map_metadata() -> Dictionary:
	"""Get the current map's metadata"""
	if current_map.is_empty():
		return {}
	return current_map.get("metadata", {})

func list_all_maps() -> Array:
	"""List all available map files with their previews"""
	var maps = MapLoader.list_available_maps()
	var previews = []
	
	for map_path in maps:
		var preview = MapLoader.get_map_preview(map_path)
		preview["path"] = map_path
		previews.append(preview)
	
	return previews

func validate_current_map() -> Dictionary:
	"""Validate the currently loaded map"""
	if current_map.is_empty():
		return {"valid": false, "errors": ["No map loaded"], "warnings": []}
	return MapLoader.validate_map(current_map)

func export_current_map(file_path: String) -> bool:
	"""Export the currently loaded map to a file"""
	if current_map.is_empty():
		push_error("[MapManager] No map to export")
		return false
	return MapLoader.save_map_to_file(current_map, file_path)

func reload_map() -> Dictionary:
	"""Reload the current map (useful for procedural regeneration)"""
	if current_map.is_empty():
		return load_random_map_file()
	
	# If it was a procedurally generated map, generate a new one with same style
	if current_map.has("style"):
		var style_name = current_map.style
		var style_enum = MapGenerator.MapStyle.CLASSIC
		
		# Convert string back to enum
		for i in MapGenerator.MapStyle.keys().size():
			if MapGenerator.MapStyle.keys()[i] == style_name:
				style_enum = i as MapGenerator.MapStyle
				break
		
		return generate_procedural_map(style_enum, current_map.width, current_map.height)
	
	# Otherwise, reload from file (just return current since files don't change)
	return current_map
