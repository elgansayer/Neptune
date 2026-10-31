extends "res://tests/bot_test_suite.gd"

const Runtime = preload("res://shared/runtime_config.gd")
const Arena = preload("res://shared/content/arena_pack_loader.gd")
const STANDARD := "res://demo/packs/standard/manifest.json"
const WIDE := "res://demo/packs/wide/manifest.json"
const LINKED := "res://demo/packs/linked/manifest.json"
var room: GameInstance
var previous_config: Dictionary

func setup_suite() -> void: pass
func teardown_suite() -> void: pass

func setup_test() -> void:
	previous_config = {"tile_size": GameConfig.TILE_SIZE, "width": GameConfig.map_width,
		"height": GameConfig.map_height, "name": GameConfig.map_name, "spawn_points": GameConfig.spawn_points.duplicate()}

func teardown_test() -> void:
	if is_instance_valid(room): room.queue_free()
	await get_tree().process_frame
	GameConfig.load_map_config(previous_config)

func _room(paths: Array, arena: String, local_map: String = "") -> GameInstance:
	room = load("res://tests/support/fixture_game_instance.gd").new()
	room.room_pack_paths = paths.duplicate()
	room.room_arena_id = arena
	room.room_map_path = local_map
	room.room_capacity_request = {"seats": 4, "preset_limit": 4}
	room.countdown_time = 0
	add_child(room)
	room.set_physics_process(false)
	if is_instance_valid(room.bot_manager): room.bot_manager.set_physics_process(false)
	return room

func _expected_lock(paths: Array) -> Dictionary:
	var identities: Array = []
	for path in paths:
		var text := FileAccess.get_file_as_string(path)
		var manifest: Dictionary = JSON.parse_string(text)
		identities.append({"pack_id": manifest.pack_id, "version": manifest.version, "manifest_sha256": text.sha256_text()})
	identities.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a.pack_id < b.pack_id)
	return {"schema": "neptune.manifest-lock.v1", "roots": identities.duplicate(true), "packs": identities.duplicate(true)}

func test_legacy_startup_defaults_and_explicit_json_selection_remain_available() -> Variant:
	var defaults := Runtime.parse_arguments([], "res://main_server.tscn")
	var json := Runtime.parse_arguments(["--room-map=res://maps/neptune_standard.json"], "res://main_server.tscn")
	return assert_true(defaults.error.is_empty() and defaults.role == "server" and defaults.room_pack_paths.is_empty()
		and defaults.room_arena.is_empty() and json.error.is_empty() and json.room_map == "res://maps/neptune_standard.json",
		"Registered arenas must not alter omitted defaults or existing JSON selection")

func test_cli_selects_one_arena_from_multiple_explicit_manifests() -> Variant:
	var config := Runtime.parse_arguments(["--room-pack=" + STANDARD, "--room-pack=" + WIDE,
		"--room-arena=example.wide:arena", "--room-seats=4"], "res://main_server.tscn")
	return assert_true(config.error.is_empty() and config.room_pack_paths == [STANDARD, WIDE]
		and config.room_arena == "example.wide:arena" and config.room_seats == 4,
		"Repeatable manifest inputs and explicit arena identity must reach startup together")

func test_cli_refuses_ambiguous_incomplete_and_noncanonical_selections() -> Variant:
	var paired := ["--room-pack=" + STANDARD, "--room-arena=example.standard:arena"]
	var cases: Array = [["--room-pack"], ["--room-pack=" + STANDARD], ["--room-arena=example.standard:arena"],
		paired + ["--room-pack=" + STANDARD], paired + ["--room-arena=example.standard:arena"],
		paired + ["--room-map=res://maps/neptune_standard.json"]]
	for path in ["/tmp/manifest.json", "https://example.com/manifest.json", "res://../manifest.json", "res://packs/./manifest.json",
		"res://packs//manifest.json", "res://packs\\manifest.json", "user://packs/../manifest.json", "res://packs/manifest.pck", "res://"]:
		cases.append(["--room-pack=" + path, "--room-arena=example.standard:arena"])
	for id in ["arena", ":arena", "example:", "example::arena", "example..pack:arena", "Example:arena", "example:../arena"]:
		cases.append(["--room-pack=" + STANDARD, "--room-arena=" + id])
	for arguments in cases:
		if Runtime.parse_arguments(arguments).error.is_empty(): return "Invalid startup selection accepted: " + str(arguments)
	return true

func test_cli_bounds_manifest_count_and_accepts_user_storage() -> Variant:
	var arguments: Array = ["--room-arena=example.standard:arena"]
	for index in 32: arguments.append("--room-pack=user://packs/pack%d/manifest.json" % index)
	if not Runtime.parse_arguments(arguments).error.is_empty(): return "Bounded user-storage manifest inputs were rejected"
	arguments.append("--room-pack=user://packs/overflow/manifest.json")
	return assert_true(not Runtime.parse_arguments(arguments).error.is_empty(), "Manifest count must be bounded before loading")

func test_selected_pack_arena_uses_existing_geometry_collision_and_admission() -> Variant:
	var game := _room([STANDARD, WIDE], "example.standard:arena")
	var original := MapLoader.load_map_from_file("res://maps/neptune_standard.json")
	if not game.room_setup_result.accepted: return "Pack arena could not prepare a real room: " + str(game.room_setup_result)
	if game.game_map != original.grid or game.spawn_points != original.spawn_points: return "Registered map changed existing fixture geometry/spawns"
	if game.map_tiles.is_empty() or not is_instance_valid(game.bot_manager): return "Registered arena bypassed production collision/bot setup"
	var human := game.add_player(701, "Creator")
	var bot := game.spawn_bot("BALANCED")
	return assert_true(human.accepted and bot.accepted and human.cell != bot.cell
		and game.room_content_descriptor.content_id == "example.standard:arena" and game.room_content_selection.size() == 2,
		"Selected content must retain real admission and both additive registrations")

func test_missing_or_conflicting_explicit_pack_selection_never_falls_back() -> Variant:
	var game := _room(["res://demo/packs/missing/manifest.json"], "example.missing:arena")
	if game.room_setup_result.accepted or not game.game_map.is_empty() or game.countdown_time != 0 or game.is_physics_processing():
		return "Missing explicit pack silently activated another arena"
	if not game.room_setup_result.has("field") or not game.room_setup_result.has("source"):
		return "Pack refusal lost file/field diagnostics"
	game.free()
	game = _room([STANDARD], "example.standard:arena", "res://maps/neptune_standard.json")
	if game.room_setup_result.accepted or not game.game_map.is_empty(): return "Conflicting direct setup bypassed CLI mutual exclusion"
	game.free()
	game = _room([STANDARD], "")
	return assert_true(not game.room_setup_result.accepted and game.game_map.is_empty(), "Incomplete direct setup must also refuse without fallback")

func test_public_map_configuration_is_detached_and_contains_no_source_paths() -> Variant:
	var game := _room([STANDARD, WIDE], "example.wide:arena")
	if not game.room_setup_result.accepted: return "Wide pack room failed"
	var config := game.get_room_map_config()
	if not config.render_geometry or config.width != 27 or config.content.content_id != "example.wide:arena":
		return "Public map metadata did not identify selected geometry"
	var expected := _expected_lock([STANDARD, WIDE])
	if config.get("lock", {}) != expected or config.get("lock_sha256", "") != JSON.stringify(expected, "", true).sha256_text():
		return "Public map metadata omitted the complete canonical manifest lock"
	if "res://" in JSON.stringify(config) or "user://" in JSON.stringify(config): return "Local manifest path escaped into public metadata"
	config.content["content_id"] = "changed:arena"
	config.selection.clear()
	config.lock.roots[0]["manifest_sha256"] = "0".repeat(64)
	config.lock.packs.clear()
	config["lock_sha256"] = "0".repeat(64)
	return assert_true(game.room_content_descriptor.content_id == "example.wide:arena" and game.room_content_selection.size() == 2
		and game.room_content_lock == expected and game.room_content_lock_sha256 == JSON.stringify(expected, "", true).sha256_text(),
		"Clients cannot mutate the authority's selected pack records through detached metadata")

func test_dependent_pack_room_resolves_before_existing_collision_and_bot_setup() -> Variant:
	var paths: Array = [LINKED, WIDE, STANDARD]
	var game := _room(paths, "example.linked:arena")
	if not game.room_setup_result.accepted: return "Dependent root could not prepare room: " + str(game.room_setup_result)
	var original := MapLoader.load_map_from_file("res://demo/packs/linked/arena.json")
	var expected := _expected_lock(paths)
	var config := game.get_room_map_config()
	if game.game_map != original.grid or game.spawn_points != original.spawn_points or game.map_tiles.is_empty():
		return "Dependent arena bypassed existing map/collision paths"
	var human := game.add_player(701, "LinkedCreator")
	var bot := game.spawn_bot("BALANCED")
	return assert_true(human.accepted and bot.accepted and human.cell != bot.cell
		and config.content.content_id == "example.linked:arena" and config.selection == expected.packs
		and config.lock == expected and config.lock_sha256 == JSON.stringify(expected, "", true).sha256_text(),
		"Dependent root must preserve admission, explicit roots and the full resolved lock")

func test_adapter_registration_order_and_offline_expected_lock_reuse() -> Variant:
	var first := Arena.load_arena([LINKED, WIDE, STANDARD], "example.linked:arena")
	if not first.accepted: return "Dependent-first arena load failed: " + str(first)
	var reused := Arena.load_arena([STANDARD, LINKED, WIDE], "example.linked:arena", first.lock)
	if not reused.accepted: return "Offline expected-lock reuse failed: " + str(reused)
	return assert_true(first.lock == _expected_lock([STANDARD, WIDE, LINKED]) and first.lock == reused.lock
		and first.lock_sha256 == reused.lock_sha256 and first.selection == reused.selection
		and first.descriptor == reused.descriptor and first.map == reused.map,
		"Input order must not alter pinned offline selection, lock identity or selected arena")

func test_adapter_lock_mismatch_never_publishes_partial_arena_metadata() -> Variant:
	var paths: Array = [STANDARD, WIDE, LINKED]
	var loaded := Arena.load_arena(paths, "example.linked:arena")
	if not loaded.accepted: return "Offline mismatch control failed to load"
	var original := loaded.duplicate(true)
	var stale: Dictionary = loaded.lock.duplicate(true)
	stale.roots[0]["manifest_sha256"] = "0".repeat(64)
	var missing_root: Dictionary = loaded.lock.duplicate(true)
	missing_root.roots.pop_back()
	for expected in [stale, missing_root]:
		var failed := Arena.load_arena(paths, "example.linked:arena", expected)
		if failed.accepted or failed.has("map") or failed.has("descriptor") or failed.has("selection"):
			return "Mismatched offline lock exposed a partially loaded arena"
		if not failed.has("field") or not failed.has("source"): return "Lock mismatch lost file/field diagnostics"
	return assert_eq(loaded, original, "Rejected offline reuse must not mutate a previously accepted receipt")

func test_missing_dependency_refuses_room_without_fallback_or_public_lock() -> Variant:
	var game := _room([LINKED, STANDARD], "example.linked:arena")
	return assert_true(not game.room_setup_result.accepted and game.game_map.is_empty()
		and game.room_content_descriptor.is_empty() and game.room_content_selection.is_empty()
		and game.room_content_lock.is_empty() and game.room_content_lock_sha256.is_empty()
		and game.countdown_time == 0 and not game.is_physics_processing()
		and game.room_setup_result.has("field") and game.room_setup_result.has("source"),
		"A missing pinned dependency must fail before collision, bot setup or content publication")

func test_local_json_room_keeps_legacy_snapshot_without_pack_lock_fields() -> Variant:
	var game := _room([], "", "res://maps/neptune_standard.json")
	if not game.room_setup_result.accepted: return "Existing local JSON room no longer loads"
	var config := game.get_room_map_config()
	return assert_true(config.render_geometry and not config.has("content") and not config.has("selection")
		and not config.has("lock") and not config.has("lock_sha256"), "Legacy JSON rooms cannot acquire synthetic pack identities")

func test_selected_arena_metadata_reaches_existing_client_geometry_renderer() -> Variant:
	var game := _room([STANDARD], "example.standard:arena")
	if not game.room_setup_result.accepted: return "Standard pack room failed"
	var viewport := SubViewport.new()
	viewport.size = Vector2i(320, 224)
	add_child(viewport)
	var view = load("res://client/game_view.tscn").instantiate()
	view.set_script(load("res://tests/support/arena_view_fixture.gd"))
	viewport.add_child(view)
	view.update_game_state({"map": game.game_map, "map_config": game.get_room_map_config()})
	await get_tree().process_frame
	var correct: bool = view.render_geometry and view.map_scene_instance == null and not view.block_nodes.is_empty()
	viewport.queue_free()
	await get_tree().process_frame
	return assert_true(correct, "Registered arena must render selected authoritative geometry instead of legacy Stage 1")
