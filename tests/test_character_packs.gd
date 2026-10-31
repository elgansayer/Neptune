extends "res://tests/bot_test_suite.gd"

const Characters = preload("res://shared/content/character_pack_loader.gd")
const Registry = preload("res://shared/content/session_content_registry.gd")
const RUBY := "res://demo/characters/ruby/manifest.json"
const JADE := "res://demo/characters/jade/manifest.json"
var _root := ""
var _counter := 0
var _viewports: Array[SubViewport] = []

func setup_suite() -> void:
	_root = "user://character-pack-tests-%d-%d" % [OS.get_process_id(), get_instance_id()]
	DirAccess.make_dir_recursive_absolute(_root)

func setup_test() -> void: pass

func teardown_test() -> void:
	for viewport in _viewports: viewport.queue_free()
	_viewports.clear()
	await get_tree().process_frame

func teardown_suite() -> void:
	_remove(_root)

func _remove(path: String) -> void:
	var directory := DirAccess.open(path)
	for name in directory.get_files(): DirAccess.remove_absolute(path.path_join(name))
	for name in directory.get_directories():
		var child := path.path_join(name)
		if directory.is_link(child): DirAccess.remove_absolute(child)
		else: _remove(child)
	DirAccess.remove_absolute(path)

func _write(path: String, text: String) -> void:
	var file := FileAccess.open(path, FileAccess.WRITE)
	file.store_string(text)
	file.close()

func _copy() -> String:
	_counter += 1
	var path := _root.path_join(str(_counter))
	DirAccess.make_dir_recursive_absolute(path.path_join("frames"))
	for name in ["manifest.json", "character.json", "frames/idle.rgba"]:
		var bytes := FileAccess.get_file_as_bytes(RUBY.get_base_dir().path_join(name))
		var file := FileAccess.open(path.path_join(name), FileAccess.WRITE)
		file.store_buffer(bytes)
		file.close()
	return path

func _data() -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string(RUBY.get_base_dir().path_join("character.json")))

func _update(path: String, data: Dictionary) -> void:
	_write(path.path_join("character.json"), JSON.stringify(data, "", true, true))
	_rehash(path)

func _rehash(path: String) -> void:
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path.path_join("manifest.json")))
	manifest.content[0].sha256 = FileAccess.get_sha256(path.path_join("character.json"))
	_write(path.path_join("manifest.json"), JSON.stringify(manifest))

func _view() -> Node2D:
	var viewport := SubViewport.new()
	_viewports.append(viewport)
	viewport.size = Vector2i(320, 224)
	add_child(viewport)
	var view := load("res://client/game_view.tscn").instantiate() as Node2D
	view.set_script(load("res://tests/support/arena_view_fixture.gd"))
	viewport.add_child(view)
	return view

func _actor() -> Dictionary:
	return {"position": {"x": 64, "y": 64}, "velocity": {"x": 0, "y": 0}, "facing": "DOWN", "is_dead": false}

func test_two_original_characters_coexist_in_the_existing_registry() -> Variant:
	var registry := Registry.new()
	for path in [RUBY, JADE]:
		var receipt := registry.register_manifest(FileAccess.get_file_as_string(path), path)
		if not receipt.accepted: return "Original character failed to register"
		var selected := registry.select_pack(receipt.identity.pack_id, receipt.identity.version, receipt.identity.manifest_sha256)
		if not selected.accepted: return "Characters collided"
	return registry.selection().size() == 2 and registry.resolve("example.ruby:character").accepted and registry.resolve("example.jade:character").accepted

func test_pixels_timings_anchor_and_script_free_visuals_round_trip() -> Variant:
	var loaded := Characters.load_character([RUBY, JADE], "example.ruby:character")
	if not loaded.accepted: return loaded
	var visual := Characters.create_visual(loaded)
	var sprite := visual.get_node("AnimatedSprite2D") as AnimatedSprite2D
	var pixel := sprite.sprite_frames.get_frame_texture("state_idle", 0).get_image().get_pixel(0, 0)
	var native_reference := SpriteFrames.new()
	native_reference.set_animation_speed("default", 12.3456789)
	native_reference.add_frame("default", sprite.sprite_frames.get_frame_texture("down_walk", 0), 0.123456789)
	var valid := visual.get_script() == null and sprite.get_script() == null and sprite.sprite_frames.get_script() == null and pixel == Color.RED and sprite.offset == Vector2(0, -8) and sprite.centered and sprite.animation == "state_idle" and sprite.sprite_frames.get_animation_speed("down_walk") == native_reference.get_animation_speed("default") and sprite.sprite_frames.get_frame_duration("down_walk", 0) == native_reference.get_frame_duration("default", 0)
	visual.free()
	return valid

func test_created_visuals_do_not_share_mutable_animation_state() -> Variant:
	var loaded := Characters.load_character([RUBY], "example.ruby:character")
	var first := Characters.create_visual(loaded)
	var second := Characters.create_visual(loaded)
	first.get_node("AnimatedSprite2D").sprite_frames.set_animation_speed("state_idle", 99)
	var valid: bool = second.get_node("AnimatedSprite2D").sprite_frames.get_animation_speed("state_idle") == 8 and loaded.frames.get_animation_speed("state_idle") == 8
	first.free()
	second.free()
	return valid

func test_schema_fields_flags_and_fallbacks_fail_with_diagnostics() -> Variant:
	for override in [{"schema": "neptune.character.v2"}, {"name": ""}, {"offset": [0, INF]}, {"offset": [0, 257]}, {"centered": 1}, {"flip_h": "true"}, {"fallback": "missing"}, {"script": "payload.gd"}, {"provenance": "res://payload.tres"}]:
		var data := _data()
		data.merge(override, true)
		var result := Characters.validate(data, "chosen/character.json")
		if result.accepted or result.source != "chosen/character.json" or result.field.is_empty(): return "Invalid character lacked file/field refusal"
	return true

func test_missing_duplicate_and_invalid_animation_frames_are_refused() -> Variant:
	for mutation in ["empty", "duplicate", "fps", "duration", "loop", "name", "resource"]:
		var data := _data()
		match mutation:
			"empty": data.animations[0].frames.clear()
			"duplicate": data.animations.append(data.animations[0].duplicate(true))
			"fps": data.animations[0].fps = 0
			"duration": data.animations[0].frames[0].duration = -1
			"loop": data.animations[0].loop = 1
			"name": data.animations[0].name = "state_idle\n"
			"resource": data.animations[0].frames[0]["texture"] = "res://payload.tres"
		if Characters.validate(data).accepted: return "Invalid animation accepted: " + mutation
	return true

func test_paths_dimensions_and_reference_conflicts_are_checked_before_images() -> Variant:
	for path in ["../idle.rgba", "res://idle.rgba", "/idle.rgba", "frames/../idle.rgba", "frames\\idle.rgba", "frames/idle.png", "frames/idle.gd"]:
		var data := _data()
		data.animations[0].frames[0].path = path
		if Characters.validate(data).accepted: return "Unsafe pixel path accepted"
	for dimensions in [[0, 2], [257, 2], [1.5, 2], [true, 2]]:
		var data := _data()
		data.animations[0].frames[0].width = dimensions[0]
		data.animations[0].frames[0].height = dimensions[1]
		if Characters.validate(data).accepted: return "Bad dimensions accepted"
	var data := _data()
	data.animations[1].frames[0].sha256 = "0".repeat(64)
	return Characters.validate(data).reason == "conflicting_pixel_reference"

func test_budgets_reject_excessive_animations_frames_images_and_pixels() -> Variant:
	var data := _data()
	for index in 65: data.animations.append(data.animations[0].duplicate(true))
	if Characters.validate(data).reason != "animation_budget_exceeded": return "Animation budget bypassed"
	data = _data()
	for index in 513: data.animations[0].frames.append(data.animations[0].frames[0].duplicate(true))
	if Characters.validate(data).reason != "frame_budget_exceeded": return "Frame budget bypassed"
	data = _data()
	data.animations.resize(1)
	for index in 257:
		var frame: Dictionary = data.animations[0].frames[0].duplicate(true)
		frame.path = "frames/pixel%d.rgba" % index
		data.animations[0].frames.append(frame)
	if Characters.validate(data).reason != "pixel_budget_exceeded": return "Image count budget bypassed"
	data = _data()
	data.animations.resize(1)
	data.animations[0].frames.clear()
	for index in 65:
		data.animations[0].frames.append({"path": "frames/large%d.rgba" % index, "sha256": "a".repeat(64), "width": 256, "height": 256, "duration": 1})
	return Characters.validate(data).reason == "pixel_budget_exceeded"

func test_missing_truncated_oversized_and_changed_pixel_bytes_refuse() -> Variant:
	for size in [0, 1, 20, 16]:
		var bytes := PackedByteArray()
		bytes.resize(size)
		bytes.fill(42)
		var path := _copy()
		var file := FileAccess.open(path.path_join("frames/idle.rgba"), FileAccess.WRITE)
		file.store_buffer(bytes)
		file.close()
		var result := Characters.load_character([path.path_join("manifest.json")], "example.ruby:character")
		if result.accepted or result.has("frames"): return "Invalid pixel data built a visual"
	var missing := _copy()
	DirAccess.remove_absolute(missing.path_join("frames/idle.rgba"))
	return not Characters.load_character([missing.path_join("manifest.json")], "example.ruby:character").accepted

func test_definition_hashes_duplicate_keys_and_symlink_pixels_refuse() -> Variant:
	var path := _copy()
	_write(path.path_join("character.json"), FileAccess.get_file_as_string(path.path_join("character.json")) + " ")
	if Characters.load_character([path.path_join("manifest.json")], "example.ruby:character").reason != "definition_hash_mismatch": return "Definition bytes not pinned"
	path = _copy()
	var text := FileAccess.get_file_as_string(path.path_join("character.json"))
	_write(path.path_join("character.json"), '{"name":"Duplicate",' + text.trim_prefix("{"))
	_rehash(path)
	if Characters.load_character([path.path_join("manifest.json")], "example.ruby:character").reason != "duplicate_json_key": return "Duplicate definition key accepted"
	path = _copy()
	DirAccess.remove_absolute(path.path_join("frames/idle.rgba"))
	var directory := DirAccess.open(path)
	if directory.create_link(ProjectSettings.globalize_path(RUBY.get_base_dir().path_join("frames/idle.rgba")), ProjectSettings.globalize_path(path.path_join("frames/idle.rgba"))) != OK: return "Native symlink fixture unavailable"
	return Characters.load_character([path.path_join("manifest.json")], "example.ruby:character").reason == "unsafe_definition_path"

func test_local_participants_select_distinct_visuals_without_changing_defaults() -> Variant:
	var view := _view()
	var physics := [GameConfig.TILE_SIZE, GameConfig.PLAYER_HALF_WIDTH, GameConfig.BASE_SPEED]
	if not view.select_local_character("701", [RUBY, JADE], "example.ruby:character").accepted: return "Ruby selection failed"
	if not view.select_local_character("702", [RUBY, JADE], "example.jade:character").accepted: return "Jade selection failed"
	for id in ["701", "702", "703"]: view.update_player(id, _actor())
	var ruby: AnimatedSprite2D = view.player_nodes["701"].get_meta("animated_sprite")
	var jade: AnimatedSprite2D = view.player_nodes["702"].get_meta("animated_sprite")
	var original: AnimatedSprite2D = view.player_nodes["703"].get_meta("animated_sprite")
	return ruby.sprite_frames.get_frame_texture("state_idle", 0).get_image().get_pixel(0, 0) == Color.RED and jade.sprite_frames.get_frame_texture("state_idle", 0).get_image().get_pixel(0, 0) == Color.GREEN and jade.offset == Vector2(1, -6) and original.sprite_frames.get_animation_names().size() == 36 and not view.player_nodes["703"].has_meta("character_descriptor") and physics == [GameConfig.TILE_SIZE, GameConfig.PLAYER_HALF_WIDTH, GameConfig.BASE_SPEED]

func test_bad_or_late_selection_preserves_previous_visual_and_declared_fallback() -> Variant:
	var path := _copy()
	var data := _data()
	data.animations[0].name = "rest"
	data.fallback = "rest"
	_update(path, data)
	var view := _view()
	if not view.select_local_character("701", [path.path_join("manifest.json")], "example.ruby:character").accepted: return "Custom fallback could not select"
	if view.select_local_character("701", [RUBY], "example.unknown:character").accepted: return "Missing character accepted"
	view.update_player("701", _actor())
	var sprite: AnimatedSprite2D = view.player_nodes["701"].get_meta("animated_sprite")
	return sprite.animation == "rest" and view.select_local_character("701", [JADE], "example.jade:character").reason == "visual_already_created" and view.player_nodes["701"].get_meta("animated_sprite") == sprite and not view.select_local_character("../actor", [RUBY], "example.ruby:character").accepted

func test_complete_roster_removal_clears_selection_before_peer_id_reuse() -> Variant:
	var view := _view()
	view.select_local_character("701", [RUBY], "example.ruby:character")
	view.update_player("701", _actor())
	view.update_game_state({"players": {}})
	view.update_player("701", _actor())
	return not view.player_nodes["701"].has_meta("character_descriptor")
