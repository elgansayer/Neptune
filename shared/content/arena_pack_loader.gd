extends RefCounted

## First runtime adapter: local JSON arena definitions through the existing map
## parser. No PCK, resource scene, script or downloaded code is mounted or loaded.
const Manifest = preload("res://shared/content/pack_manifest.gd")
const Registry = preload("res://shared/content/session_content_registry.gd")
const MapLoader = preload("res://shared/maps/map_loader.gd")

static func _read(path: String) -> Dictionary:
	var relative := path.substr(path.find("://") + 3)
	var prefix := "res://" if path.begins_with("res://") else "user://"
	var confined := _definition_path(prefix, relative)
	if not confined.accepted:
		return confined
	if not FileAccess.file_exists(path):
		return Manifest.failure("file_missing", "$", path)
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return Manifest.failure("file_unreadable", "$", path)
	if file.get_length() > Manifest.MAX_MANIFEST_BYTES:
		file.close()
		return Manifest.failure("json_byte_budget_exceeded", "$", path)
	var bytes := file.get_buffer(file.get_length())
	file.close()
	if not Manifest.valid_utf8(bytes):
		return Manifest.failure("invalid_utf8", "$", path)
	var text := bytes.get_string_from_utf8()
	if text.to_utf8_buffer() != bytes:
		return Manifest.failure("noncanonical_utf8", "$", path)
	return {"accepted": true, "text": text, "sha256": _digest(bytes)}

static func _digest(bytes: PackedByteArray) -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(bytes)
	return context.finish().hex_encode()

static func _definition_path(root: String, relative: String) -> Dictionary:
	var current := root
	for part in relative.split("/"):
		var directory := DirAccess.open(current)
		if directory == null or directory.is_link(part):
			return Manifest.failure("unsafe_definition_path", "content.path", root.path_join(relative))
		current = current.path_join(part)
	return {"accepted": true, "path": current}

static func _integer(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(float(value)) and floor(float(value)) == float(value)

## Preflight the untrusted JSON before invoking the legacy parser, which expects
## typed coordinates/metadata and logs engine errors for malformed terrain.
static func _check_map(data: Variant, source: String) -> Dictionary:
	if not data is Dictionary:
		return Manifest.failure("arena_not_object", "$", source)
	var grid = data.get("grid")
	if not grid is Array or grid.size() < 3 or not grid[0] is Array or grid[0].size() < 3:
		return Manifest.failure("invalid_grid", "grid", source)
	var width: int = grid[0].size()
	if grid.size() * width > 65536:
		return Manifest.failure("arena_cell_budget_exceeded", "grid", source)
	for y in grid.size():
		if not grid[y] is Array or grid[y].size() != width:
			return Manifest.failure("non_rectangular_grid", "grid[%d]" % y, source)
		for x in width:
			if not _integer(grid[y][x]) or grid[y][x] < 0 or grid[y][x] > 2:
				return Manifest.failure("invalid_terrain", "grid[%d][%d]" % [y, x], source)
	var spawns = data.get("spawn_points")
	if not spawns is Array or spawns.is_empty() or spawns.size() > 64:
		return Manifest.failure("invalid_spawns", "spawn_points", source)
	var used := {}
	for index in spawns.size():
		var spawn = spawns[index]
		var x: Variant
		var y: Variant
		if spawn is Array and spawn.size() == 2:
			x = spawn[0]
			y = spawn[1]
		elif spawn is Dictionary and spawn.has("x") and spawn.has("y") and spawn.size() == 2:
			x = spawn.x
			y = spawn.y
		else:
			return Manifest.failure("invalid_spawn", "spawn_points[%d]" % index, source)
		if not _integer(x) or not _integer(y) or x < 0 or y < 0 or x >= width or y >= grid.size():
			return Manifest.failure("invalid_spawn_coordinate", "spawn_points[%d]" % index, source)
		var cell := Vector2i(int(x), int(y))
		if grid[cell.y][cell.x] != 0 or used.has(cell):
			return Manifest.failure("blocked_or_duplicate_spawn", "spawn_points[%d]" % index, source)
		used[cell] = true
	if data.has("metadata") and not data.metadata is Dictionary:
		return Manifest.failure("invalid_metadata", "metadata", source)
	for field in ["name", "author", "description"]:
		if data.has(field) and (not data[field] is String or data[field].length() > 512):
			return Manifest.failure("invalid_arena_text", field, source)
	return {"accepted": true}

static func load_arena(manifest_paths: Array, content_id: String) -> Dictionary:
	if manifest_paths.is_empty() or manifest_paths.size() > Registry.MAX_SELECTED:
		return Manifest.failure("invalid_pack_selection", "room_pack_paths")
	if not Manifest.valid_id(content_id):
		return Manifest.failure("invalid_content_id", "room_arena")
	var registry := Registry.new()
	var seen := {}
	for path in manifest_paths:
		if not Manifest.valid_manifest_path(path) or seen.has(path):
			return Manifest.failure("invalid_or_duplicate_manifest_path", "room_pack_paths", str(path))
		seen[path] = true
		var document := _read(path)
		if not document.accepted:
			return document
		var validated := Manifest.parse(document.text, path)
		if not validated.accepted:
			return validated
		for entry in validated.manifest.content:
			if entry.kind != "arena":
				return Manifest.failure("unsupported_runtime_kind", "content.kind", path)
		var registered := registry.register_manifest(document.text, path)
		if not registered.accepted:
			return registered
		var identity: Dictionary = registered.identity
		var selected := registry.select_pack(identity.pack_id, identity.version, identity.manifest_sha256)
		if not selected.accepted:
			return selected
	var resolved := registry.resolve(content_id)
	if not resolved.accepted:
		return resolved
	var located := _definition_path(resolved.source.get_base_dir(), resolved.entry.path)
	if not located.accepted:
		return located
	var definition := _read(located.path)
	if not definition.accepted:
		return definition
	if definition.sha256 != resolved.entry.sha256:
		return Manifest.failure("definition_hash_mismatch", "content.sha256", located.path)
	var parsed := Manifest.parse_json(definition.text, located.path)
	if not parsed.accepted:
		return parsed
	var checked := _check_map(parsed.data, located.path)
	if not checked.accepted:
		return checked
	var map: Dictionary = MapLoader.parse_map_data(parsed.data, content_id)
	return {"accepted": true, "reason": "arena_loaded", "map": map,
		"descriptor": resolved.descriptor.duplicate(true), "selection": registry.selection()}
