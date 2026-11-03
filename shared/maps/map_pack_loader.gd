extends Node
class_name MapPackLoader

## Loads maps from PCK files containing TileMap data
## Reads TileMapLayer nodes to extract game logic

const Constants = preload("res://shared/constants.gd")

static func load_map_from_pck(pck_path: String) -> Dictionary:
	"""
	Load a map from a PCK file containing a TileMap-based scene
	
	Returns: {
		grid: Array[Array[int]],  # 2D array: 0=empty, 1=hard, 2=soft_slot
		spawn_points: Array[Vector2],  # World coordinates
		soft_slots: Array[Vector2i],  # Tile coordinates of possible soft blocks
		hard_blocks: Array[Vector2i],  # Tile coordinates of hard walls
		width: int,
		height: int,
		tile_size: int,
		name: String,
		metadata: Dictionary
	}
	"""
	
	# Mount the PCK
	var success = ProjectSettings.load_resource_pack(pck_path)
	if not success:
		push_error("[MapPackLoader] Failed to mount PCK: " + pck_path)
		return {}
	
	print("[MapPackLoader] Mounted PCK: ", pck_path)
	
	# Load the main scene (should be Stage.tscn or similar)
	# Try common names
	var scene_path = ""
	for potential_path in ["res://Stage.tscn", "res://Map.tscn", "res://stage.tscn"]:
		if ResourceLoader.exists(potential_path):
			scene_path = potential_path
			break
	
	if scene_path == "":
		push_error("[MapPackLoader] Could not find Stage.tscn in PCK")
		return {}
	
	var map_scene_res = load(scene_path)
	if map_scene_res == null:
		push_error("[MapPackLoader] Failed to load scene: " + scene_path)
		return {}
	
	var map_scene = map_scene_res.instantiate()
	
	# Get MapMetadata if present (check by script/name, not class type)
	var metadata_node = null
	
	# Check if root node has metadata properties
	if map_scene.has_method("get") and map_scene.get("map_name") != null:
		metadata_node = map_scene
	else:
		# Try to find MapMetadata node by name
		if map_scene.has_node("MapMetadata"):
			metadata_node = map_scene.get_node("MapMetadata")
		else:
			# Search children
			for child in map_scene.get_children():
				if child.name == "MapMetadata" or (child.get_script() != null and "MapMetadata" in str(child.get_script().get_path())):
					metadata_node = child
					break
	
	# Get TileMapLayer nodes
	var wall_floor_map: TileMapLayer = map_scene.get_node_or_null("WallAndFloorBlockMap")
	var spawn_soft_map: TileMapLayer = map_scene.get_node_or_null("SpawnAndSoftBlockMap")
	
	if wall_floor_map == null or spawn_soft_map == null:
		push_error("[MapPackLoader] Missing TileMapLayer nodes")
		map_scene.queue_free()
		return {}
	
	# Parse the TileMaps
	var result = _parse_tilemaps(wall_floor_map, spawn_soft_map, metadata_node)
	
	# Clean up
	map_scene.queue_free()
	
	print("[MapPackLoader] Loaded map: ", result.name, " (", result.width, "x", result.height, ")")
	print("[MapPackLoader] Found ", result.hard_blocks.size(), " hard blocks, ", 
		  result.soft_slots.size(), " soft slots, ", result.spawn_points.size(), " spawns")
	
	return result

static func _parse_tilemaps(wall_floor: TileMapLayer, spawn_soft: TileMapLayer, metadata) -> Dictionary:
	"""Parse TileMapLayer data into game-usable format"""
	
	# Get map dimensions from the TileMaps
	var wall_rect = wall_floor.get_used_rect()
	var spawn_rect = spawn_soft.get_used_rect()
	
	# Use the larger rect to be safe
	var map_rect = wall_rect.merge(spawn_rect)
	var width = map_rect.size.x
	var height = map_rect.size.y
	var offset = map_rect.position
	
	# Get tile size (assume 16x16 from your project, but could read from tileset)
	var tile_size = 16
	if metadata != null:
		var meta_tile_size = metadata.get("tile_size")
		if meta_tile_size != null:
			tile_size = meta_tile_size
	
	# No scale factor - use native tile size throughout
	# Initialize result
	var grid = []
	var hard_blocks = []
	var soft_slots = []
	var spawn_points = []
	
	# Create grid array
	for y in range(height):
		var row = []
		for x in range(width):
			row.append(0)  # Default to empty
		grid.append(row)
	
	# Parse WallAndFloorBlockMap (hard walls and floor)
	for y in range(height):
		for x in range(width):
			var tile_coord = Vector2i(x + offset.x, y + offset.y)
			var source_id = wall_floor.get_cell_source_id(tile_coord)
			
			if source_id == 1:  # Hard block (source 1 in your tileset)
				grid[y][x] = 1
				hard_blocks.append(Vector2i(x, y))
			elif source_id == 0:  # Floor/walkable
				grid[y][x] = 0
	
	# Parse SpawnAndSoftBlockMap (soft slots and spawns)
	for y in range(height):
		for x in range(width):
			var tile_coord = Vector2i(x + offset.x, y + offset.y)
			var source_id = spawn_soft.get_cell_source_id(tile_coord)
			
			if source_id == 0:  # Soft block slot (source 0 in soft map)
				if grid[y][x] != 1:  # Don't override hard blocks
					grid[y][x] = 2
					soft_slots.append(Vector2i(x, y))
			elif source_id == 1:  # Spawn point (source 1 in soft map)
				# Convert tile position to world coordinates (native tile size)
				var world_x = (x * tile_size) + (tile_size / 2.0)
				var world_y = (y * tile_size) + (tile_size / 2.0)
				spawn_points.append(Vector2(world_x, world_y))
	
	# Build result
	var result = {
		"grid": grid,
		"spawn_points": spawn_points,
		"soft_slots": soft_slots,
		"hard_blocks": hard_blocks,
		"width": width,
		"height": height,
		"tile_size": tile_size,  # Use native tile size from map
		"name": "Unknown Map",
		"metadata": {}
	}
	
	# Add metadata if available
	if metadata != null:
		var map_name = metadata.get("map_name")
		if map_name != null:
			result.name = map_name
		result.metadata = {
			"id": metadata.get("map_id") if metadata.get("map_id") != null else "unknown",
			"version": metadata.get("version") if metadata.get("version") != null else "",
			"author": metadata.get("author") if metadata.get("author") != null else "Unknown",
			"description": metadata.get("description") if metadata.get("description") != null else "",
			"theme": metadata.get("theme") if metadata.get("theme") != null else "classic",
			"recommended_players": metadata.get("recommended_players") if metadata.get("recommended_players") != null else "2-4",
			"difficulty": metadata.get("difficulty") if metadata.get("difficulty") != null else "medium"
		}
	
	return result

static func reserve_casual_spawn_clearance(active_slots: Array, spawn_points: Array, tile_size: float) -> Array:
	# The development room samples optional destructibles. Keep a two-cell
	# radius free at each declared start so ordinary range-one players and the
	# existing safe-plant bot controller can turn out of their first blast lane.
	# This filters optional soft slots only; authored hard geometry is untouched.
	var reserved := {}
	for position in spawn_points:
		var cell := Vector2i(floori(position.x / tile_size), floori(position.y / tile_size))
		for y in range(cell.y - 2, cell.y + 3):
			for x in range(cell.x - 2, cell.x + 3): reserved[Vector2i(x, y)] = true
	var result := []
	for slot in active_slots:
		if not reserved.has(slot): result.append(slot)
	return result

static func choose_soft_block_pattern(soft_slots: Array, pattern: String = "RANDOM_70", density: float = 0.7) -> Array:
	"""
	Choose which soft block slots to activate based on a pattern
	
	Patterns:
	- FULL: Use all slots
	- RANDOM_XX: Random percentage (e.g., RANDOM_70 = 70%)
	- SPARSE: 30% random
	- MEDIUM: 50% random
	- DENSE: 80% random
	- CHECKERBOARD: Alternating grid pattern
	- OUTER_RING: Only slots near edges
	- CENTER: Only slots in center area
	"""
	
	var active_slots: Array = []
	
	match pattern:
		"FULL":
			active_slots = soft_slots.duplicate()
		
		"SPARSE":
			for slot in soft_slots:
				if randf() < 0.3:
					active_slots.append(slot)
		
		"MEDIUM":
			for slot in soft_slots:
				if randf() < 0.5:
					active_slots.append(slot)
		
		"DENSE":
			for slot in soft_slots:
				if randf() < 0.8:
					active_slots.append(slot)
		
		"CHECKERBOARD":
			for slot in soft_slots:
				if (slot.x + slot.y) % 2 == 0:
					active_slots.append(slot)
		
		"OUTER_RING":
			# Assume map width/height from slots (approximate)
			var max_x = 0
			var max_y = 0
			for slot in soft_slots:
				max_x = max(max_x, slot.x)
				max_y = max(max_y, slot.y)
			
			for slot in soft_slots:
				if slot.x < 4 or slot.x > max_x - 4 or slot.y < 3 or slot.y > max_y - 3:
					active_slots.append(slot)
		
		"CENTER":
			var max_x = 0
			var max_y = 0
			for slot in soft_slots:
				max_x = max(max_x, slot.x)
				max_y = max(max_y, slot.y)
			
			var center_x = max_x / 2
			var center_y = max_y / 2
			
			for slot in soft_slots:
				if abs(slot.x - center_x) < max_x * 0.3 and abs(slot.y - center_y) < max_y * 0.3:
					active_slots.append(slot)
		
		_:  # Default to RANDOM_XX
			var target_density = density
			if pattern.begins_with("RANDOM_"):
				var percent_str = pattern.substr(7)  # After "RANDOM_"
				target_density = float(percent_str) / 100.0
			
			for slot in soft_slots:
				if randf() < target_density:
					active_slots.append(slot)
	
	return active_slots
