extends "res://tests/bot_test_suite.gd"

## Actual GameView/HUD presentation for the authoritative round envelope.
## Original fixture geometry; these are Neptune demo, not Saturn timing claims.
var viewport: SubViewport
var view: Node2D
var old_config: Dictionary

func setup_suite() -> void: pass
func teardown_suite() -> void: pass

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

func _snapshot(epoch: int, phase: String, tick: int = 1, with_map: bool = false) -> Dictionary:
	var state := {"round": {"epoch": epoch, "phase": phase, "remaining": 3.0,
		"result": {"winner_id": "42", "reason": "survivors"} if phase == "results" else {}},
		"simulation_tick": tick, "server_time": tick * 16.0, "a": phase == "active", "p": {}, "b": {}}
	if with_map:
		state["map"] = [[1, 1, 1], [1, 0, 1], [1, 1, 1]]
		state["map_config"] = {"tile_size": 16, "width": 3, "height": 3, "name": "Round fixture", "render_geometry": true}
	return state

func test_new_epoch_resets_result_effects_dead_registry_and_original_map() -> Variant:
	view.update_game_state(_snapshot(1, "results", 90, true))
	if not view.match_ended or not view.hud.game_over_shown: return "Actual results were not presented"
	var original_signature: String = view.map_signature
	view.removed_dead_players["42"] = true
	view.input_buffer.append("ui_right")
	view._explosion_timeline.seen["old-event"] = {"start_time": 0.0}
	for collection in [view.bomb_nodes, view.explosion_nodes, view.powerup_nodes,
			view.egg_nodes, view.tirra_nodes, view.hurry_pending_shadows]:
		var old_node := Node2D.new()
		view.add_child(old_node)
		collection["old"] = old_node
	view.update_game_state(_snapshot(2, "countdown", 1, true))
	return assert_true(view.round_epoch == 2 and view.map_epoch == 2 and view.map_generation == 2
		and view.map_signature == original_signature and view.map_rendered
		and not view.match_ended and view.match_winner_id.is_empty()
		and not view.hud.game_over_shown and view.hud.get_node_or_null("WinnerLabel") == null
		and view.removed_dead_players.is_empty() and view.input_buffer.is_empty()
		and view._explosion_timeline.seen.is_empty() and view.bomb_nodes.is_empty()
		and view.explosion_nodes.is_empty() and view.powerup_nodes.is_empty()
		and view.egg_nodes.is_empty() and view.tirra_nodes.is_empty()
		and view.hurry_pending_shadows.is_empty(), "Fresh rounds must reset the actual client world and terminal HUD")

func test_previous_epoch_cannot_restore_old_results_or_effect_clock() -> Variant:
	view.update_game_state(_snapshot(2, "active", 4, true))
	view.update_game_state(_snapshot(1, "results", 900, true))
	return assert_true(view.round_epoch == 2 and view.round_phase == "active"
		and not view.match_ended and not view.hud.game_over_shown
		and view._explosion_timeline.last_tick == 4 and view.map_generation == 1,
		"A late previous-authority packet must not affect this round")

func test_reliable_map_after_newer_state_does_not_rewind_phase() -> Variant:
	view.update_game_state(_snapshot(3, "active", 20))
	view.update_game_state(_snapshot(3, "countdown", 1, true))
	return assert_true(view.map_rendered and view.map_epoch == 3
		and view.round_phase == "active" and view._last_round_tick == 20
		and "Battle" in view.hud.round_status.text, "Reliable arena delivery must survive an overtaking state packet without rewinding its phase")

func test_waiting_and_countdown_are_not_terminal_results() -> Variant:
	view.update_game_state(_snapshot(1, "waiting", 1, true))
	if view.match_ended or view.hud.game_over_shown: return "Waiting was mistaken for game over"
	view.update_game_state(_snapshot(1, "countdown", 2))
	return assert_true(not view.match_ended and not view.hud.game_over_shown
		and view.hud.countdown_label.visible and view.hud.countdown_label.text == "3",
		"Explicit inactive state must be interpreted through the authoritative phase")

func test_old_countdown_callbacks_cannot_hide_next_round_countdown() -> Variant:
	view.hud.show_countdown(0.2)
	view.hud.reset_round()
	view.hud.show_countdown(3.0)
	await get_tree().create_timer(1.0).timeout
	return assert_true(view.hud.countdown_label.visible and view.hud.countdown_label.text == "3"
		and view.hud.last_countdown_value == 3 and view.hud.controls_visible(),
		"Presentation callbacks from a previous round cannot hide the new countdown or controls")

func test_rpc_intake_requires_valid_current_epoch_on_negotiated_round_protocol() -> Variant:
	var client := get_node("/root/ClientMain")
	var old_protocol: int = client.negotiated_protocol
	var old_epoch: int = client.current_round_epoch
	client.negotiated_protocol = 3
	client.current_round_epoch = 0
	var accepted: bool = client._accept_round_epoch(_snapshot(2, "active"))
	var rejects: bool = not client._accept_round_epoch(_snapshot(1, "results")) and not client._accept_round_epoch({})
	var malformed := _snapshot(3, "active")
	malformed.round.remaining = -1.0
	rejects = rejects and not client._accept_round_epoch(malformed)
	client.negotiated_protocol = old_protocol
	client.current_round_epoch = old_epoch
	return assert_true(accepted and rejects, "Only authenticated current-epoch envelope data may reach presentation")

func test_directional_mount_frames_do_not_query_missing_default_animation() -> Variant:
	var actor := Node2D.new()
	view.add_child(actor)
	var mount := Node2D.new()
	mount.name = "TirraVisual"
	actor.add_child(mount)
	var sprite := AnimatedSprite2D.new()
	var frames := SpriteFrames.new()
	frames.remove_animation("default")
	frames.add_animation("down_stopped")
	var image := Image.create(1, 1, false, Image.FORMAT_RGBA8)
	frames.add_frame("down_stopped", ImageTexture.create_from_image(image))
	sprite.sprite_frames = frames
	sprite.animation = "down_stopped"
	mount.add_child(sprite)
	view._update_tirra_visual(actor, {"tirra_growth_level": 0}, "up", false)
	return assert_true(sprite.animation == "down_stopped", "Mounted directional resources do not require a default/idle animation")

func test_real_hurry_warning_initializes_falling_visual_before_setup() -> Variant:
	view.update_game_state(_snapshot(1, "active", 1, true))
	view._spawn_hurry_block_with_warning(1, 1, "1,1")
	var shadow = view.hurry_pending_shadows["1,1"]
	shadow.shadow_warning_complete.emit()
	var falling = view.hurry_falling_blocks.get("1,1")
	return assert_true(falling != null and falling.is_node_ready() and falling.is_falling
		and falling.block_visual.get_child_count() == 1 and falling.position.y < falling.target_y,
		"Hurry visuals must initialize children and drop dimensions before setup on native and Web")

func test_previous_round_hurry_callbacks_and_camera_tween_are_cancelled() -> Variant:
	view.update_game_state(_snapshot(1, "active", 1, true))
	view._spawn_hurry_block_with_warning(1, 1, "1,1")
	var shadow = view.hurry_pending_shadows["1,1"]
	view._shake_camera_on_impact()
	var old_tween: Tween = view._camera_impact_tween
	view.update_game_state(_snapshot(2, "countdown", 1, true))
	shadow.shadow_warning_complete.emit()
	return assert_true(not old_tween.is_running() and view.camera.offset == Vector2.ZERO
		and view.hurry_falling_blocks.is_empty() and view.hurry_pending_shadows.is_empty(),
		"Retired warning callbacks and shake tweens cannot populate the fresh round")

func test_demo_footer_and_participant_labels_fit_the_native_viewport() -> Variant:
	view.hud.add_player_face("42", "Bot", 0, {"type": "bot", "personality": "BALANCED"})
	await get_tree().process_frame
	var controls: Rect2 = view.hud.controls_label.get_global_rect()
	var status: Rect2 = view.hud.round_status.get_global_rect()
	var face = view.hud.player_face_slots[view.hud.player_face_mapping["42"]].get_node("FaceViewport")
	var badge: Label = face.get_node("BotBadge")
	return assert_true(view.hud.controls_visible() and viewport.get_visible_rect().encloses(status)
		and not status.intersects(controls) and face.get_global_rect().encloses(badge.get_global_rect()),
		"Focus/build/bot labels must fit 320x224: controls=%s status=%s face=%s badge=%s" % [controls, status, face.get_global_rect(), badge.get_global_rect()])
