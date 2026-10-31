extends "res://tests/bot_test_suite.gd"

const Registry = preload("res://shared/content/pack_registry.gd")
const Manifest = preload("res://shared/content/pack_manifest.gd")
const ORCHARD := "res://tests/fixtures/content/orchard"
const RIVER := "res://tests/fixtures/content/river"
var registry: Registry
var _root := ""
var _counter := 0
var _rooms: Array[Node] = []

func setup_suite() -> void:
	_root = "user://pack-registry-tests-%d-%d" % [OS.get_process_id(), get_instance_id()]
	DirAccess.make_dir_recursive_absolute(_root)

func setup_test() -> void:
	registry = Registry.new()

func teardown_test() -> void:
	for room in _rooms:
		room.queue_free()
	_rooms.clear()
	await get_tree().process_frame
	await get_tree().process_frame

func teardown_suite() -> void:
	_remove_tree(_root)

func _remove_tree(path: String) -> void:
	var directory := DirAccess.open(path)
	for file in directory.get_files():
		DirAccess.remove_absolute(path.path_join(file))
	for folder in directory.get_directories():
		var child := path.path_join(folder)
		if not directory.is_link(child): _remove_tree(child)
		else: DirAccess.remove_absolute(child)
	DirAccess.remove_absolute(path)

func _write(path: String, text: String) -> void:
	var file := FileAccess.open(path, FileAccess.WRITE)
	file.store_string(text)
	file.close()

func _copy(source: String) -> String:
	_counter += 1
	var path := _root.path_join(str(_counter))
	DirAccess.make_dir_recursive_absolute(path)
	for file in ["pack.json", "arena.json"]:
		_write(path.path_join(file), FileAccess.get_file_as_string(source.path_join(file)))
	return path

func _json(path: String) -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string(path))

func _save_manifest(path: String, manifest: Dictionary) -> void:
	_write(path.path_join("pack.json"), JSON.stringify(manifest))

func _save_map(path: String, data: Dictionary) -> void:
	_write(path.path_join("arena.json"), JSON.stringify(data))
	var manifest := _json(path.path_join("pack.json"))
	manifest.content[0].sha256 = FileAccess.get_sha256(path.path_join("arena.json"))
	_save_manifest(path, manifest)

func test_two_original_packs_coexist_through_existing_map_manager() -> Variant:
	if not registry.register_directory(ORCHARD).ok or not registry.register_directory(RIVER).ok:
		return "Original fixtures did not register"
	if registry.list_maps() != PackedStringArray(["example.orchard:arena", "example.river:arena"]):
		return "Namespaced additions did not coexist"
	var manager := MapManager.new()
	var first := manager.load_registered_map(registry, "example.orchard:arena")
	var second := manager.load_registered_map(registry, "example.river:arena")
	var before := manager.current_map.duplicate(true)
	var missing := manager.load_registered_map(registry, "neptune.base:arena")
	var unchanged := manager.current_map == before
	manager.free()
	return first.grid[3][3] == 1 and second.grid[3][3] == 2 and second.spawn_points[0] == Vector2(24, 24) and missing.is_empty() and unchanged

func test_registration_and_detached_reads_cannot_mutate_defaults_or_each_other() -> Variant:
	var manager := MapManager.new()
	manager.load_map(MapManager.MapSource.FILE, "res://maps/classic_arena.json")
	var baseline := manager.current_map.duplicate(true)
	registry.register_directory(ORCHARD)
	var map_copy := registry.get_map("example.orchard:arena")
	map_copy.grid[1][1] = 1
	map_copy.metadata.content_identity.id = "changed"
	var manifest_copy := registry.get_manifest("example.orchard")
	manifest_copy.content.clear()
	var retained := registry.get_map("example.orchard:arena")
	var unchanged := manager.current_map == baseline
	manager.free()
	return unchanged and retained.grid[1][1] == 0 and retained.metadata.content_identity.id == "example.orchard:arena" and registry.get_manifest("example.orchard").content.size() == 1

func test_duplicate_pack_and_later_version_cannot_replace_selected_content() -> Variant:
	registry.register_directory(ORCHARD)
	var before := registry.get_map("example.orchard:arena")
	if registry.register_directory(ORCHARD).error.code != "duplicate_id": return "Duplicate pack accepted"
	var path := _copy(ORCHARD)
	var manifest := _json(path.path_join("pack.json"))
	manifest.version = "2.0.0"
	_save_manifest(path, manifest)
	var other_session := Registry.new()
	return registry.register_directory(path).error.code == "duplicate_id" and registry.get_map("example.orchard:arena") == before and other_session.register_directory(path).ok and other_session.get_map("example.orchard:arena").metadata.content_identity.version == "2.0.0"

func test_manifest_diagnostics_name_the_precise_field() -> Variant:
	var base := _json(ORCHARD.path_join("pack.json"))
	for change in [["schema", "neptune.pack/2", "unsupported_schema"], ["id", "neptune.overwrite", "reserved_namespace"],
		["id", "Unscoped", "invalid_id"], ["id", "example.orchard\n", "invalid_id"], ["version", "latest", "invalid_version"], ["version", "1.0.0\n", "invalid_version"], ["author", "", "invalid_text"],
		["license", true, "invalid_text"], ["dependencies", {}, "invalid_dependencies"], ["content", [], "invalid_content"]]:
		var candidate := base.duplicate(true)
		candidate[change[0]] = change[1]
		var result := Manifest.validate(candidate, "chosen/pack.json")
		if result.ok or result.error.code != change[2] or result.error.file != "chosen/pack.json" or result.error.field != "$." + change[0]:
			return "Bad diagnostic for " + change[0]
	return true

func test_manifest_rejects_duplicate_ids_paths_foreign_ids_and_executables() -> Variant:
	var base := _json(ORCHARD.path_join("pack.json"))
	for property in ["id", "path"]:
		var candidate := base.duplicate(true)
		candidate.content.append(candidate.content[0].duplicate(true))
		if property == "path": candidate.content[1].id += "-two"
		var result := Manifest.validate(candidate)
		if result.ok or result.error.field != "$.content[1]." + property: return "Duplicate " + property + " accepted"
	for path in ["../arena.json", "sub/../arena.json", "/arena.json", "res://arena.json", "a\\arena.json", "Arena.json", "con.json", "arena.gd", "arena.tscn", "arena.so", "arena.pck"]:
		var candidate := base.duplicate(true)
		candidate.content[0].path = path
		if Manifest.validate(candidate).ok: return "Unsafe path accepted: " + path
	var foreign := base.duplicate(true)
	foreign.content[0].id = "example.river:arena"
	return not Manifest.validate(foreign).ok

func test_unknown_fields_types_and_noncanonical_digests_are_rejected() -> Variant:
	var base := _json(ORCHARD.path_join("pack.json"))
	var unknown := base.duplicate(true)
	unknown.script = "payload.gd"
	if Manifest.validate(unknown).error.code != "unknown_field": return "Unknown schema field accepted"
	for entry in [{"type": "character"}, {"type": "script"}, {"sha256": "latest"}, {"sha256": "a".repeat(64) + "\n"}, {"sha256": true}]:
		var candidate := base.duplicate(true)
		candidate.content[0].merge(entry, true)
		if Manifest.validate(candidate).ok: return "Unsupported content declaration accepted"
	return true

func test_missing_and_incompatible_dependencies_have_no_side_effects() -> Variant:
	var path := _copy(RIVER)
	var manifest := _json(path.path_join("pack.json"))
	manifest.dependencies = [{"id": "example.orchard", "version": "1.0.0"}]
	_save_manifest(path, manifest)
	if registry.register_directory(path).error.code != "missing_dependency" or not registry.list_maps().is_empty(): return "Missing dependency changed state"
	registry.register_directory(ORCHARD)
	manifest.dependencies[0].version = "2.0.0"
	_save_manifest(path, manifest)
	if registry.register_directory(path).error.code != "dependency_version" or registry.list_maps().size() != 1: return "Wrong version changed state"
	manifest.dependencies[0].version = "1.0.0"
	_save_manifest(path, manifest)
	return registry.register_directory(path).ok and registry.list_maps().size() == 2

func test_failed_second_entry_publishes_nothing_and_retains_existing_pack() -> Variant:
	registry.register_directory(ORCHARD)
	var before := registry.get_map("example.orchard:arena")
	var path := _copy(RIVER)
	var manifest := _json(path.path_join("pack.json"))
	var second: Dictionary = manifest.content[0].duplicate(true)
	second.id += "-two"
	second.path = "missing.json"
	manifest.content.append(second)
	_save_manifest(path, manifest)
	var result := registry.register_directory(path)
	return not result.ok and result.error.code == "missing_file" and registry.get_manifest("example.river").is_empty() and registry.get_map("example.river:arena").is_empty() and registry.get_map("example.orchard:arena") == before

func test_content_mutation_is_detected_before_registration_and_ignored_after_snapshot() -> Variant:
	var path := _copy(ORCHARD)
	registry.register_directory(path)
	var before := registry.get_map("example.orchard:arena")
	_write(path.path_join("arena.json"), FileAccess.get_file_as_string(path.path_join("arena.json")) + " ")
	var fresh := Registry.new()
	var result := fresh.register_directory(path)
	return not result.ok and result.error.code == "hash_mismatch" and fresh.list_maps().is_empty() and registry.get_map("example.orchard:arena") == before

func test_duplicate_json_keys_including_escaped_keys_are_rejected() -> Variant:
	var path := _copy(ORCHARD)
	_write(path.path_join("duplicate.json"), '{"id":1,"\\u0069d":2}')
	var result := Manifest.read_json(path.path_join("duplicate.json"), 1024)
	if result.ok or result.error.code != "duplicate_json_key": return "Duplicate key silently won"
	_write(path.path_join("strings.json"), '{"text":"brackets { [ and escaped \\" quotes","nested":{"id":1},"id":2}')
	return Manifest.read_json(path.path_join("strings.json"), 1024).ok

func test_missing_malformed_and_oversized_json_are_refused() -> Variant:
	var path := _copy(ORCHARD)
	for text in ["", "{", "x".repeat(Manifest.MAX_MANIFEST_BYTES + 1)]:
		_write(path.path_join("pack.json"), text)
		if registry.register_directory(path).ok or not registry.list_maps().is_empty(): return "Malformed or oversized pack accepted"
	return registry.register_directory(path.path_join("absent")).error.code == "missing_directory"

func test_invalid_utf8_is_rejected_without_native_decoder_errors() -> Variant:
	var path := _copy(ORCHARD)
	for bytes in [PackedByteArray([0xff]), PackedByteArray([0xc0, 0xaf]), PackedByteArray([0xed, 0xa0, 0x80]), PackedByteArray([0xf4, 0x90, 0x80, 0x80]), PackedByteArray([0xe2, 0x82])]:
		var file := FileAccess.open(path.path_join("pack.json"), FileAccess.WRITE)
		file.store_buffer(bytes)
		file.close()
		if registry.register_directory(path).error.code != "invalid_utf8": return "Malformed UTF-8 accepted"
	return true

func test_international_author_text_round_trips_canonical_utf8() -> Variant:
	var path := _copy(ORCHARD)
	var manifest := _json(path.path_join("pack.json"))
	manifest.author = "Éowyn Ω 中 😀"
	_save_manifest(path, manifest)
	return registry.register_directory(path).ok and registry.get_manifest("example.orchard").author == manifest.author

func test_content_byte_and_grid_budgets_preserve_existing_registrations() -> Variant:
	registry.register_directory(ORCHARD)
	var before := registry.get_map("example.orchard:arena")
	var path := _copy(RIVER)
	_write(path.path_join("arena.json"), "x".repeat(Manifest.MAX_DATA_BYTES + 1))
	if registry.register_directory(path).error.code != "file_budget": return "Oversized map reached decoding"
	var data := _json(RIVER.path_join("arena.json"))
	data.grid[0].resize(257)
	_save_map(path, data)
	return registry.register_directory(path).error.code == "map_budget" and registry.list_maps().size() == 1 and registry.get_map("example.orchard:arena") == before

func test_bad_map_coordinates_cells_and_nested_resources_are_rejected() -> Variant:
	for alteration in ["fractional_spawn", "duplicate_spawn", "wall_spawn", "fractional_cell", "row_width", "script", "metadata"]:
		var path := _copy(ORCHARD)
		var data := _json(path.path_join("arena.json"))
		match alteration:
			"fractional_spawn": data.spawn_points[0].x = 1.5
			"duplicate_spawn": data.spawn_points[1] = data.spawn_points[0].duplicate()
			"wall_spawn": data.spawn_points[0].x = 0
			"fractional_cell": data.grid[2][2] = 0.5
			"row_width": data.grid[2].pop_back()
			"script": data["script"] = "res://payload.gd"
			"metadata": data.metadata = "resource.tres"
		_save_map(path, data)
		if registry.register_directory(path).ok or not registry.list_maps().is_empty(): return "Invalid map accepted: " + alteration
	return true

func test_symlinked_file_subdirectory_and_root_are_refused() -> Variant:
	var path := _copy(ORCHARD)
	var directory := DirAccess.open(_root)
	var target := ProjectSettings.globalize_path(path.path_join("arena.json"))
	DirAccess.remove_absolute(path.path_join("arena.json"))
	if directory.create_link(ProjectSettings.globalize_path(ORCHARD.path_join("arena.json")), target) != OK: return "Cannot create native symlink fixture"
	if registry.register_directory(path).error.code != "symlink": return "Symlink file followed"
	var link := _root.path_join("linked-root")
	if directory.create_link(ProjectSettings.globalize_path(ORCHARD), ProjectSettings.globalize_path(link)) != OK: return "Cannot create root symlink fixture"
	if registry.register_directory(link + "/").error.code != "symlink": return "Symlink root followed"
	var nested := _copy(RIVER)
	var manifest := _json(nested.path_join("pack.json"))
	manifest.content[0].path = "linked/arena.json"
	_save_manifest(nested, manifest)
	if directory.create_link(ProjectSettings.globalize_path(ORCHARD), ProjectSettings.globalize_path(nested.path_join("linked"))) != OK: return "Cannot create subdirectory symlink"
	return registry.register_directory(nested).error.code == "symlink"

func test_trusted_stage_export_registers_without_rewriting_original_or_output() -> Variant:
	var path := _root.path_join("stage-export")
	var original := FileAccess.get_sha256("res://maps/stage1.pck")
	var arguments := PackedStringArray(["--headless", "--path", ProjectSettings.globalize_path("res://"),
		"--script", "res://tools/asset_audit/export_map_pack.gd", "--", "--trusted-pck=res://maps/stage1.pck",
		"--output=" + path, "--id=example.stage-one", "--version=1.0.0", "--author=Neptune",
		"--license=LicenseRef-Private", "--provenance=Trusted-local-stage-conversion"])
	var output := []
	if OS.execute(OS.get_executable_path(), arguments, output, true) != 0:
		return "Trusted stage conversion failed: " + str(output)
	if not registry.register_directory(path).ok: return "Export cannot register through the public map boundary"
	var map := registry.get_map("example.stage-one:arena")
	if map.width != 21 or map.height != 14 or map.spawn_points.size() != 4:
		return "Existing stage dimensions or spawns were not preserved"
	var before := FileAccess.get_sha256(path.path_join("arena.json"))
	var manifest := FileAccess.get_sha256(path.path_join("pack.json"))
	output.clear()
	if OS.execute(OS.get_executable_path(), arguments, output, true) != 1 or not "Output already exists" in str(output):
		return "Author export overwrote an existing version directory"
	return FileAccess.get_sha256(path.path_join("arena.json")) == before and FileAccess.get_sha256(path.path_join("pack.json")) == manifest and FileAccess.get_sha256("res://maps/stage1.pck") == original

func test_actual_room_selects_data_only_map_and_admits_real_actors() -> Variant:
	var room := load("res://tests/support/fixture_game_instance.gd").new() as GameInstance
	_rooms.append(room)
	room.room_pack_directory = ORCHARD
	room.room_map_id = "example.orchard:arena"
	room.countdown_time = 0.0
	room.room_capacity_request = {"seats": 4, "preset_limit": 4}
	add_child(room)
	if not room.room_setup_result.accepted or room.game_map.size() != 7 or room.room_content_identity.id != room.room_map_id:
		return "Production room selection failed: " + JSON.stringify(room.room_setup_result)
	if not room.add_player(-901, "Human").accepted or not room.spawn_bot("BALANCED").accepted:
		return "Real actor/bot admission failed on selected map"
	return room.players.size() == 2 and room.spawn_points.size() == 4

func test_unknown_map_and_invalid_pack_refuse_without_legacy_fallback() -> Variant:
	for selection in [[ORCHARD, "example.orchard:missing", "unknown_room_map_id"], [ORCHARD.path_join("missing"), "example.orchard:arena", "invalid_room_pack"]]:
		var room := load("res://tests/support/fixture_game_instance.gd").new() as GameInstance
		_rooms.append(room)
		room.room_pack_directory = selection[0]
		room.room_map_id = selection[1]
		room.countdown_time = 0.0
		room.room_capacity_request = {"seats": 4, "preset_limit": 4}
		add_child(room)
		if room.room_setup_result.accepted or room.room_setup_result.reason != selection[2] or not room.game_map.is_empty() or room.match_active:
			return "Explicit failed pack selection fell back or started a match"
	return true
