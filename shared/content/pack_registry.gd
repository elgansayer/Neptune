extends RefCounted
class_name PackRegistry

const Manifest = preload("res://shared/content/pack_manifest.gd")
const Maps = preload("res://shared/maps/map_loader.gd")

var _packs := {}
var _maps := {}

func register_directory(directory: String) -> Dictionary:
	var manifest_file := directory.path_join("pack.json")
	var read := _read_local(directory, "pack.json", Manifest.MAX_MANIFEST_BYTES)
	if not read.ok: return read
	var validated := Manifest.validate(read.data, manifest_file)
	if not validated.ok: return validated
	var manifest: Dictionary = validated.manifest
	if _packs.has(manifest.id):
		return Manifest.failure(manifest_file, "$.id", "duplicate_id", "This session already selected a version of this pack")
	for index in range(manifest.dependencies.size()):
		var dependency: Dictionary = manifest.dependencies[index]
		var field := "$.dependencies[%d]" % index
		if not _packs.has(dependency.id):
			return Manifest.failure(manifest_file, field + ".id", "missing_dependency", "Register dependency " + dependency.id + " first")
		if _packs[dependency.id].version != dependency.version:
			return Manifest.failure(manifest_file, field + ".version", "dependency_version", "Require " + dependency.id + "@" + dependency.version)
	var pending := {}
	var total := 0
	for index in range(manifest.content.size()):
		var entry: Dictionary = manifest.content[index]
		if _maps.has(entry.id):
			return Manifest.failure(manifest_file, "$.content[%d].id" % index, "duplicate_id", "Content cannot replace an existing registration")
		var path := directory.path_join(entry.path)
		var content := _read_local(directory, entry.path, Manifest.MAX_DATA_BYTES)
		if not content.ok: return content
		total += content.bytes
		if total > 16 * 1024 * 1024:
			return Manifest.failure(path, "$", "pack_budget", "Pack JSON exceeds the 16 MiB total budget")
		if content.sha256 != entry.sha256:
			return Manifest.failure(manifest_file, "$.content[%d].sha256" % index, "hash_mismatch", "Declared content hash differs from " + entry.path)
		var checked := validate_map(content.data, path)
		if not checked.ok: return checked
		var map_data: Dictionary = Maps.parse_map_data(content.data)
		map_data.metadata["content_identity"] = {"pack": manifest.id, "version": manifest.version,
			"manifest_sha256": read.sha256, "id": entry.id, "sha256": entry.sha256}
		pending[entry.id] = map_data
	# Publish only after every entry and dependency passes. No filesystem writes.
	_packs[manifest.id] = manifest.duplicate(true)
	_maps.merge(pending, false)
	return {"ok": true, "pack": manifest.id, "version": manifest.version, "manifest_sha256": read.sha256}

func get_map(content_id: String) -> Dictionary:
	return _maps.get(content_id, {}).duplicate(true)

func get_manifest(pack_id: String) -> Dictionary:
	return _packs.get(pack_id, {}).duplicate(true)

func list_maps() -> PackedStringArray:
	var ids := PackedStringArray(_maps.keys())
	ids.sort()
	return ids

static func _read_local(directory: String, relative: String, budget: int) -> Dictionary:
	directory = directory.simplify_path().trim_suffix("/")
	var root := DirAccess.open(directory)
	if root == null: return Manifest.failure(directory, "$", "missing_directory", "Pack directory does not exist")
	var path := directory
	# Check both the root and every relative component. Never follow pack symlinks.
	var ancestor := ProjectSettings.globalize_path(directory).simplify_path()
	while ancestor != ancestor.get_base_dir():
		if root.is_link(ancestor): return Manifest.failure(directory, "$", "symlink", "Pack root and its ancestors cannot be symlinks")
		ancestor = ancestor.get_base_dir()
	for part in relative.split("/"):
		path = path.path_join(part)
		if root.is_link(path): return Manifest.failure(path, "$", "symlink", "Pack files and subdirectories cannot be symlinks")
	return Manifest.read_json(path, budget)

static func _integer(value: Variant, minimum: int, maximum: int) -> bool:
	return (value is int or value is float) and is_finite(float(value)) and value >= minimum and value <= maximum and floor(float(value)) == float(value)

static func validate_map(value: Variant, file: String) -> Dictionary:
	if not value is Dictionary: return Manifest.failure(file, "$", "invalid_map", "Expected a map object")
	var shape := Manifest.fields(value, ["schema", "name", "grid", "spawn_points", "metadata"], file, "$")
	if not shape.ok: return shape
	if value.schema != "neptune.map/1": return Manifest.failure(file, "$.schema", "unsupported_schema", "Supported map schema: neptune.map/1")
	if not value.name is String or value.name.strip_edges().is_empty() or value.name.length() > 128:
		return Manifest.failure(file, "$.name", "invalid_name", "Require a non-empty map name of at most 128 characters")
	if not value.metadata is Dictionary: return Manifest.failure(file, "$.metadata", "invalid_metadata", "Expected a metadata object")
	if not value.grid is Array or value.grid.size() < 3 or value.grid.size() > 256 or not value.grid[0] is Array or value.grid[0].size() < 3 or value.grid[0].size() > 256:
		return Manifest.failure(file, "$.grid", "map_budget", "Require a 3..256 by 3..256 grid")
	var width: int = value.grid[0].size()
	for y in range(value.grid.size()):
		if not value.grid[y] is Array or value.grid[y].size() != width:
			return Manifest.failure(file, "$.grid[%d]" % y, "invalid_grid", "Rows must have equal widths")
		for x in range(width):
			if not _integer(value.grid[y][x], 0, 2):
				return Manifest.failure(file, "$.grid[%d][%d]" % [y, x], "invalid_tile", "Terrain must be integral 0, 1 or 2")
	if not value.spawn_points is Array or value.spawn_points.is_empty() or value.spawn_points.size() > 256:
		return Manifest.failure(file, "$.spawn_points", "invalid_spawns", "Require 1..256 explicit spawn points")
	var cells := {}
	for index in range(value.spawn_points.size()):
		var spawn = value.spawn_points[index]
		var field := "$.spawn_points[%d]" % index
		if not spawn is Dictionary: return Manifest.failure(file, field, "invalid_spawn", "Expected an x/y tile coordinate")
		shape = Manifest.fields(spawn, ["x", "y"], file, field)
		if not shape.ok: return shape
		if not _integer(spawn.x, 0, width - 1): return Manifest.failure(file, field + ".x", "invalid_spawn", "Require an in-bounds integral coordinate")
		if not _integer(spawn.y, 0, value.grid.size() - 1): return Manifest.failure(file, field + ".y", "invalid_spawn", "Require an in-bounds integral coordinate")
		var cell := Vector2i(int(spawn.x), int(spawn.y))
		if value.grid[cell.y][cell.x] != 0 or cells.has(cell):
			return Manifest.failure(file, field, "blocked_or_duplicate_spawn", "Spawns must be distinct empty cells")
		cells[cell] = true
	return {"ok": true}
