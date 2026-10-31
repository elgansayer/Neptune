extends "res://tests/bot_test_suite.gd"

const Arenas = preload("res://shared/content/arena_pack_loader.gd")
var _root := ""
var _counter := 0

func setup_suite() -> void:
	_root = "user://stage-export-tests-%d-%d" % [OS.get_process_id(), get_instance_id()]
	DirAccess.make_dir_recursive_absolute(_root)

func setup_test() -> void:
	pass

func teardown_test() -> void:
	pass

func teardown_suite() -> void:
	_remove_tree(_root)

func _remove_tree(path: String) -> void:
	var directory := DirAccess.open(path)
	for file in directory.get_files(): DirAccess.remove_absolute(path.path_join(file))
	for child in directory.get_directories(): _remove_tree(path.path_join(child))
	DirAccess.remove_absolute(path)

func _destination() -> String:
	_counter += 1
	return _root.path_join(str(_counter))

func _arguments(path: String, overrides: Dictionary = {}, omit: String = "") -> PackedStringArray:
	var options := {"--trusted-pck": "res://maps/stage1.pck", "--output": path,
		"--id": "example.stage-one:pack", "--version": "1.0.0", "--author": "Neptune",
		"--license": "LicenseRef-Private", "--provenance": "Trusted local stage conversion"}
	options.merge(overrides, true)
	var args := PackedStringArray(["--headless", "--path", ProjectSettings.globalize_path("res://"),
		"--script", "res://tools/asset_audit/export_map_pack.gd", "--"])
	for key in options:
		if key != omit: args.append(key + "=" + str(options[key]))
	return args

func _run(arguments: PackedStringArray) -> Dictionary:
	var output := []
	var code := OS.execute(OS.get_executable_path(), arguments, output, true)
	return {"code": code, "output": "\n".join(output)}

func _export(path: String) -> Dictionary:
	var result := _run(_arguments(path))
	if result.code != 0 or "ERROR:" in result.output: return {"accepted": false, "output": result.output}
	return Arenas.load_arena([path.path_join("manifest.json")], "example.stage-one:arena")

func test_existing_stage_exports_through_the_merged_arena_runtime() -> Variant:
	var path := _destination()
	var original := FileAccess.get_sha256("res://maps/stage1.pck")
	var result := _export(path)
	if not result.accepted: return "Trusted conversion failed: " + str(result)
	var walls := 0
	var soft := 0
	for row in result.map.grid:
		for cell in row:
			if cell == 1: walls += 1
			elif cell == 2: soft += 1
	return result.map.width == 21 and result.map.height == 14 and result.map.spawn_points.size() == 4 and walls == 147 and soft == 135 and FileAccess.get_sha256("res://maps/stage1.pck") == original

func test_exact_identity_and_provenance_survive_runtime_loading() -> Variant:
	var path := _destination()
	var result := _export(path)
	if not result.accepted: return "Export did not register"
	return result.descriptor.pack_id == "example.stage-one:pack" and result.descriptor.content_id == "example.stage-one:arena" and result.descriptor.version == "1.0.0" and result.descriptor.sha256 == FileAccess.get_sha256(path.path_join("arena.json")) and result.descriptor.manifest_sha256 == FileAccess.get_sha256(path.path_join("manifest.json")) and result.map.metadata.version == "1.0" and result.map.metadata.authoring_source_sha256 == FileAccess.get_sha256("res://maps/stage1.pck") and result.map.metadata.authoring_provenance == "Trusted local stage conversion"

func test_existing_version_output_is_never_overwritten() -> Variant:
	var path := _destination()
	if not _export(path).accepted: return "Control export failed"
	var map_hash := FileAccess.get_sha256(path.path_join("arena.json"))
	var manifest_hash := FileAccess.get_sha256(path.path_join("manifest.json"))
	var refusal := _run(_arguments(path))
	return refusal.code == 1 and "Output already exists" in refusal.output and FileAccess.get_sha256(path.path_join("arena.json")) == map_hash and FileAccess.get_sha256(path.path_join("manifest.json")) == manifest_hash

func test_trust_acknowledgement_is_required_before_reading_a_pck() -> Variant:
	var path := _destination()
	var result := _run(_arguments(path, {}, "--trusted-pck"))
	return result.code == 1 and "Required option: --trusted-pck" in result.output and not DirAccess.dir_exists_absolute(path)

func test_missing_trusted_input_does_not_create_a_partial_output() -> Variant:
	var path := _destination()
	var result := _run(_arguments(path, {"--trusted-pck": "res://maps/missing-stage.pck"}))
	return result.code == 1 and "Trusted source is missing" in result.output and not DirAccess.dir_exists_absolute(path)

func test_reserved_ids_and_bad_versions_refuse_before_creating_output() -> Variant:
	for overrides in [{"--id": "neptune.override:pack"}, {"--version": "latest"}, {"--license": ""}, {"--provenance": "  "}, {"--provenance": "x".repeat(513)}]:
		var path := _destination()
		if _run(_arguments(path, overrides)).code != 1 or DirAccess.dir_exists_absolute(path):
			return "Invalid author metadata created an output"
	return true

func test_unknown_duplicate_and_unsafe_output_options_are_rejected() -> Variant:
	for suffix in ["--unknown=value", "--id=example.duplicate:pack"]:
		var path := _destination()
		var args := _arguments(path)
		args.append(suffix)
		if _run(args).code != 1 or DirAccess.dir_exists_absolute(path): return "Unknown/duplicate option accepted"
	var result := _run(_arguments("user://stage-export-tests/../unsafe-output"))
	return result.code == 1 and "Output must be a portable" in result.output

func test_exported_bytes_remain_hash_bound_after_registration() -> Variant:
	var path := _destination()
	if not _export(path).accepted: return "Control export failed"
	var file := FileAccess.open(path.path_join("arena.json"), FileAccess.READ_WRITE)
	file.seek_end()
	file.store_string(" ")
	file.close()
	var result := Arenas.load_arena([path.path_join("manifest.json")], "example.stage-one:arena")
	return not result.accepted and result.reason == "definition_hash_mismatch"
