extends "res://tests/bot_test_suite.gd"

const Runtime = preload("res://shared/runtime_config.gd")
const STANDARD := "res://demo/packs/standard/manifest.json"
const WIDE := "res://demo/packs/wide/manifest.json"
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
	if "res://" in JSON.stringify(config) or "user://" in JSON.stringify(config): return "Local manifest path escaped into public metadata"
	config.content["content_id"] = "changed:arena"
	config.selection.clear()
	return assert_true(game.room_content_descriptor.content_id == "example.wide:arena" and game.room_content_selection.size() == 2,
		"Clients cannot mutate the authority's selected pack records through detached metadata")

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
