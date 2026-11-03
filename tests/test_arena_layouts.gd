extends "res://tests/bot_test_suite.gd"

const Framing = preload("res://client/arena_framing.gd")
var viewport: SubViewport
var view: Node2D
var old_config: Dictionary

func setup_suite() -> void:
	pass

func teardown_suite() -> void:
	pass

func setup_test() -> void:
	old_config = {"tile_size": GameConfig.TILE_SIZE, "width": GameConfig.map_width, "height": GameConfig.map_height, "name": GameConfig.map_name}
	viewport = SubViewport.new()
	viewport.size = Vector2i(320, 224)
	add_child(viewport)
	view = load("res://client/game_view.tscn").instantiate()
	view.set_script(load("res://tests/support/arena_view_fixture.gd"))
	viewport.add_child(view)

func teardown_test() -> void:
	viewport.queue_free()
	await get_tree().process_frame
	GameConfig.load_map_config(old_config)

func _load_arena(name: String) -> Dictionary:
	var data := MapLoader.load_map_from_file("res://maps/neptune_%s.json" % name)
	view.update_game_state({"map": data.grid, "map_config": {"tile_size": 16, "width": data.width, "height": data.height, "name": data.name, "render_geometry": true}})
	return data

func _fits(inset: float) -> bool:
	view.camera.force_update_scroll()
	var origin: Vector2 = viewport.canvas_transform * Vector2.ZERO
	var end: Vector2 = viewport.canvas_transform * view.arena_pixel_size
	return origin.x >= 3.9 and origin.y >= inset + 3.9 and end.x <= viewport.size.x - 3.9 and end.y <= viewport.size.y - 42.0 - 3.9

func test_standard_arena_renders_authoritative_geometry_and_fits_below_hud() -> Variant:
	var data := _load_arena("standard")
	await get_tree().process_frame
	return assert_true(_fits(24) and view.map_scene_instance == null and view.block_nodes.size() == 1
		and GameConfig.TILE_SIZE == 16 and data.width == 15, "Standard arena must fit its geometry below a screen-pinned HUD")

func test_wide_arena_is_not_cropped_or_stretched() -> Variant:
	var data := _load_arena("wide")
	await get_tree().process_frame
	return assert_true(_fits(24) and view.camera.zoom.x == view.camera.zoom.y and view.camera.zoom.x < 1
		and data.width == 27 and GameConfig.TILE_SIZE == 16 and not view.hud.follow_viewport_enabled,
		"Wide geometry must fit uniformly without changing authoritative tile size or moving the HUD")

func test_viewport_resize_reframes_the_loaded_arena() -> Variant:
	_load_arena("wide")
	var before: Vector2 = view.camera.zoom
	viewport.size = Vector2i(480, 320)
	await get_tree().process_frame
	await get_tree().process_frame
	return assert_true(_fits(24) and view.camera.zoom.x > before.x, "Resize must refit an existing arena")

func test_second_roster_row_reserves_space_above_arena() -> Variant:
	_load_arena("standard")
	var before: Vector2 = view.camera.zoom
	var players := {}
	var participants := {}
	for i in range(12):
		players[str(i)] = {}
		participants[str(i)] = {"type": "bot"}
	view.hud.update_player_roster(players, participants)
	await get_tree().process_frame
	return assert_true(_fits(44) and view.camera.zoom.x < before.x and not view.hud.follow_viewport_enabled,
		"A twelve-participant HUD must not cover the arena")

func test_destroyed_geometry_block_is_removed_without_a_duplicate_visual() -> Variant:
	var data := _load_arena("wide")
	var block: ColorRect = view.block_nodes["13,5"].block
	data.grid[5][13] = 0
	view.update_blocks(data.grid)
	await get_tree().process_frame
	return assert_true(view.block_nodes.is_empty() and not is_instance_valid(block), "Destroyed soft block left a duplicate fallback visual")

func test_invalid_or_minimized_dimensions_cannot_change_camera() -> Variant:
	for geometry in [Vector2.ZERO, Vector2(-1, 20), Vector2(INF, 20)]:
		if Framing.fit(geometry, Vector2(320, 224), 24).accepted: return "Invalid arena dimensions accepted"
	for screen in [Vector2.ZERO, Vector2(320, 24), Vector2(NAN, 224)]:
		if Framing.fit(Vector2(240, 208), screen, 24).accepted: return "Invalid viewport dimensions accepted"
	_load_arena("wide")
	var before: Vector2 = view.camera.zoom
	view.arena_pixel_size = Vector2.ZERO
	view._update_arena_framing()
	return assert_eq(view.camera.zoom, before, "Absent map must not reset a valid camera")

func test_both_layouts_admit_mixed_players_and_keep_preset_capacity_independent() -> Variant:
	for name in ["standard", "wide"]:
		var game: GameInstance = load("res://tests/support/fixture_game_instance.gd").new()
		game.room_map_path = "res://maps/neptune_%s.json" % name
		game.room_capacity_request = {"seats": 4, "preset_limit": 4}
		game.countdown_time = 0
		add_child(game)
		game.set_physics_process(false)
		game.bot_manager.set_physics_process(false)
		var cells := {}
		var accepted: bool = game.room_setup_result.accepted
		for i in range(2):
			var receipt: Dictionary = game.add_player(701 + i, "Fixture")
			accepted = accepted and receipt.accepted
			if receipt.accepted: cells[str(receipt.cell)] = true
		for i in range(2):
			var receipt: Dictionary = game.spawn_bot("BALANCED")
			accepted = accepted and receipt.accepted
			if receipt.accepted: cells[str(receipt.cell)] = true
		var capacity: Dictionary = game.get_room_capacity()
		var refused: Dictionary = game.add_player(709, "Extra")
		game.queue_free()
		await get_tree().process_frame
		if not accepted or cells.size() != 4 or capacity.seats != 4 or capacity.preset_limit != 4 or capacity.protocol_limit != 12 or refused.accepted:
			return "Layout width changed capacity or failed distinct mixed-player admission: " + name
	return true
