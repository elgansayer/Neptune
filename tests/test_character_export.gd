extends "res://tests/bot_test_suite.gd"

const Characters = preload("res://shared/content/character_pack_loader.gd")
var _root := ""
var _counter := 0

func setup_suite() -> void:
	_root = "user://character-export-tests-%d-%d" % [OS.get_process_id(), get_instance_id()]
	DirAccess.make_dir_recursive_absolute(_root)

func setup_test() -> void: pass
func teardown_test() -> void: pass
func teardown_suite() -> void: _remove(_root)

func _remove(path: String) -> void:
	var directory := DirAccess.open(path)
	for name in directory.get_files(): DirAccess.remove_absolute(path.path_join(name))
	for name in directory.get_directories(): _remove(path.path_join(name))
	DirAccess.remove_absolute(path)

func _destination() -> String:
	_counter += 1
	return _root.path_join(str(_counter))

func _arguments(path: String, overrides: Dictionary = {}, omit: String = "") -> PackedStringArray:
	var options := {"--trusted-pck": "res://characters/player-robin-hood.pck", "--output": path,
		"--id": "example.avatar:pack", "--version": "1.0.0", "--author": "Neptune",
		"--license": "LicenseRef-Private", "--provenance": "Trusted local character conversion", "--name": "Robin Hood"}
	options.merge(overrides, true)
	var args := PackedStringArray(["--headless", "--path", ProjectSettings.globalize_path("res://"),
		"--script", "res://tools/asset_audit/export_character_pack.gd", "--"])
	for key in options:
		if key != omit: args.append(key + "=" + str(options[key]))
	return args

func _run(args: PackedStringArray) -> Dictionary:
	var output := []
	var code := OS.execute(OS.get_executable_path(), args, output, true)
	return {"code": code, "output": "\n".join(output)}

func _oracle(pack: String) -> Dictionary:
	var empty := _root.path_join("oracle")
	DirAccess.make_dir_recursive_absolute(empty)
	var file := FileAccess.open(empty.path_join("project.godot"), FileAccess.WRITE)
	file.store_string("config_version=5\n")
	file.close()
	var result := _run(PackedStringArray(["--headless", "--path", ProjectSettings.globalize_path(empty),
		"--script", ProjectSettings.globalize_path("res://tools/asset_audit/check_character_pack.gd"),
		"--", "--pack=" + ProjectSettings.globalize_path(pack)]))
	if result.code != 0 or "ERROR:" in result.output: return {}
	for line in result.output.split("\n"):
		if line.begins_with("{"):
			var parsed = JSON.parse_string(line)
			if parsed is Dictionary and parsed.has("presentation_sha256"): return parsed
	return {}

func _files(path: String) -> Dictionary:
	var result := {}
	var directory := DirAccess.open(path)
	for name in directory.get_files(): result[name] = FileAccess.get_sha256(path.path_join(name))
	for name in directory.get_directories(): result[name] = _files(path.path_join(name))
	return result

func _fixture_pack(color: Color, format: Image.Format = Image.FORMAT_RGBA8) -> Dictionary:
	var path := _destination()
	DirAccess.make_dir_recursive_absolute(path)
	var actor := Node2D.new()
	var sprite := AnimatedSprite2D.new()
	sprite.name = "AnimatedSprite2D"
	actor.add_child(sprite)
	sprite.owner = actor
	sprite.offset = Vector2(1.25, -7.5)
	sprite.centered = false
	sprite.flip_h = true
	sprite.flip_v = true
	var image := Image.create(2, 2, false, format)
	image.fill(color)
	var frames := SpriteFrames.new()
	frames.remove_animation("default")
	frames.add_animation("state_idle")
	frames.set_animation_speed("state_idle", 12.3456789)
	frames.add_frame("state_idle", ImageTexture.create_from_image(image), 0.123456789)
	sprite.sprite_frames = frames
	var packed := PackedScene.new()
	var code := packed.pack(actor)
	actor.free()
	var scene_path := path.path_join("player.tscn")
	if code != OK or ResourceSaver.save(packed, scene_path) != OK: return {}
	var pck_path := path.path_join("source.pck")
	var packer := PCKPacker.new()
	if packer.pck_start(ProjectSettings.globalize_path(pck_path)) != OK or packer.add_file("res://player.tscn", ProjectSettings.globalize_path(scene_path)) != OK or packer.flush() != OK: return {}
	return {"path": pck_path, "fps": frames.get_animation_speed("state_idle"), "duration": frames.get_frame_duration("state_idle", 0)}

func test_existing_robin_hood_matches_the_independent_authoring_oracle() -> Variant:
	var path := _destination()
	var before := FileAccess.get_sha256("res://characters/player-robin-hood.pck")
	var result := _run(_arguments(path))
	if result.code != 0 or "ERROR:" in result.output: return result.output
	var oracle := _oracle("res://characters/player-robin-hood.pck")
	var loaded := Characters.load_character([path.path_join("manifest.json")], "example.avatar:character")
	return not oracle.is_empty() and loaded.accepted and loaded.frames.get_animation_names().size() == 36 and oracle.frame_uses == 77 and oracle.presentation_sha256 == "45aa601ba8d012906ad9ef4641b734b7f35e0408fcf64324876d05ed69697c28" and Characters.presentation_hash(loaded.frames) == oracle.presentation_sha256 and str(loaded.offset) == oracle.sprite_offset and loaded.provenance.source_sha256 == before and FileAccess.get_sha256("res://characters/player-robin-hood.pck") == before

func test_original_fixture_preserves_fractional_timing_offsets_centering_and_flips() -> Variant:
	var source := _fixture_pack(Color.BLUE)
	if source.is_empty(): return "Could not build original trusted source fixture"
	var path := _destination()
	var result := _run(_arguments(path, {"--trusted-pck": source.path}))
	if result.code != 0 or "ERROR:" in result.output: return result.output
	var oracle := _oracle(source.path)
	var loaded := Characters.load_character([path.path_join("manifest.json")], "example.avatar:character")
	var valid: bool = loaded.accepted and not oracle.is_empty() and loaded.presentation_sha256 == oracle.presentation_sha256 and loaded.offset == Vector2(1.25, -7.5) and not loaded.centered and loaded.flip_h and loaded.flip_v and loaded.frames.get_animation_speed("state_idle") == source.fps and loaded.frames.get_frame_duration("state_idle", 0) == source.duration
	if not valid: return {"oracle": oracle, "loaded_hash": loaded.get("presentation_sha256"), "offset": loaded.get("offset"), "centered": loaded.get("centered"), "fps": loaded.frames.get_animation_speed("state_idle"), "source": source, "duration": loaded.frames.get_frame_duration("state_idle", 0)}
	return true

func test_source_pixel_mutation_changes_presentation_instead_of_reusing_default_pack() -> Variant:
	var signatures := []
	for color in [Color.RED, Color.BLUE]:
		var source := _fixture_pack(color)
		if source.is_empty(): return "Original source fixture unavailable"
		var path := _destination()
		if _run(_arguments(path, {"--trusted-pck": source.path})).code != 0: return "Fixture export failed"
		var loaded := Characters.load_character([path.path_join("manifest.json")], "example.avatar:character")
		if not loaded.accepted: return loaded
		signatures.append(loaded.presentation_sha256)
	return true if signatures[0] != signatures[1] else "Source colors produced identical signatures: " + str(signatures)

func test_existing_output_and_original_source_bytes_are_preserved() -> Variant:
	var path := _destination()
	var args := _arguments(path)
	var original := FileAccess.get_sha256("res://characters/player-robin-hood.pck")
	if _run(args).code != 0: return "Control export failed"
	var before := _files(path)
	var refused := _run(args)
	return refused.code == 1 and "Output already exists" in refused.output and before == _files(path) and FileAccess.get_sha256("res://characters/player-robin-hood.pck") == original

func test_higher_precision_source_is_refused_instead_of_silently_quantized() -> Variant:
	var source := _fixture_pack(Color.BLUE, Image.FORMAT_RGBAF)
	if source.is_empty(): return "HDR source fixture unavailable"
	var path := _destination()
	var result := _run(_arguments(path, {"--trusted-pck": source.path}))
	return result.code == 1 and "8-bit image" in result.output and not DirAccess.dir_exists_absolute(path)

func test_trust_options_metadata_and_fallback_fail_before_writing() -> Variant:
	var path := _destination()
	if _run(_arguments(path, {}, "--trusted-pck")).code != 1 or DirAccess.dir_exists_absolute(path): return "Implicit source trust accepted"
	for overrides in [{"--id": "neptune.override:pack"}, {"--version": "latest"}, {"--name": ""}, {"--provenance": " "}, {"--fallback": "unknown"}]:
		path = _destination()
		if _run(_arguments(path, overrides)).code != 1 or DirAccess.dir_exists_absolute(path): return "Invalid creator data produced output"
	var args := _arguments(path)
	args.append("--id=example.duplicate:pack")
	return _run(args).code == 1 and not DirAccess.dir_exists_absolute(path)
