extends "res://tests/bot_test_suite.gd"

## Synthetic production-presentation checks. No transport, local input latency,
## browser compatibility or Saturn fidelity claims follow from these samples.
const Interpolator = preload("res://client/prediction/entity_interpolator.gd")
var _owned: Array[Node] = []


func setup_suite() -> void: pass
func setup_test() -> void: pass
func teardown_suite() -> void: pass

func teardown_test() -> void:
	for node in _owned:
		if is_instance_valid(node): node.queue_free()
	_owned.clear()
	await get_tree().process_frame


func _interpolator() -> Node:
	var interpolator := Interpolator.new()
	_owned.append(interpolator)
	add_child(interpolator)
	return interpolator


func _view() -> Node2D:
	var viewport := SubViewport.new()
	viewport.size = Vector2i(320, 224)
	_owned.append(viewport)
	add_child(viewport)
	var view := load("res://client/game_view.tscn").instantiate() as Node2D
	view.set_script(load("res://tests/support/arena_view_fixture.gd"))
	viewport.add_child(view)
	view.set_process(false)
	return view


func _actor(view: Node, id: String = "20") -> Node2D:
	var actor := Node2D.new()
	var sprite := AnimatedSprite2D.new()
	sprite.name = "AnimatedSprite2D"
	sprite.sprite_frames = SpriteFrames.new()
	for animation in ["state_defeat", "down_stopped", "down_walk"]:
		sprite.sprite_frames.add_animation(animation)
	actor.add_child(sprite)
	actor.set_meta("animated_sprite", sprite)
	view.players_container.add_child(actor)
	view.player_nodes[id] = actor
	var interpolator := Interpolator.new()
	view.add_child(interpolator)
	view.remote_player_interpolators[id] = interpolator
	return actor


func _state(position: Vector2, velocity: Vector2, dead := false) -> Dictionary:
	return {"position": {"x": position.x, "y": position.y},
		"velocity": {"x": velocity.x, "y": velocity.y}, "is_dead": dead}


func test_empty_singleton_and_reset_do_not_invent_motion() -> Variant:
	var interpolator := _interpolator()
	if interpolator.get_interpolated_position(1.0) != Vector2.ZERO: return "Empty history moved"
	interpolator.add_server_state(Vector2(100, 80), Vector2(120, 0), 1.0)
	if interpolator.get_interpolated_position(20.0) != Vector2(100, 80): return "Singleton invented a trajectory"
	interpolator.reset()
	return interpolator.state_buffer.is_empty() and interpolator.get_interpolated_position(20.0) == Vector2.ZERO


func test_history_is_bounded_and_rejects_nonincreasing_timestamps() -> Variant:
	var interpolator := _interpolator()
	for index in range(40):
		interpolator.add_server_state(Vector2(index, 0), Vector2.ZERO, 10.0 + index * 0.05)
	var size: int = interpolator.state_buffer.size()
	interpolator.add_server_state(Vector2(999, 0), Vector2.ZERO, 11.95)
	interpolator.add_server_state(Vector2(999, 0), Vector2.ZERO, 11.0)
	return size <= 12 and interpolator.state_buffer.size() == size and interpolator.state_buffer.back().position == Vector2(39, 0)


func test_render_time_before_oldest_holds_first_sample_even_after_a_turn() -> Variant:
	var interpolator := _interpolator()
	interpolator.add_server_state(Vector2(100, 100), Vector2(120, 0), 10.0)
	interpolator.add_server_state(Vector2(106, 100), Vector2(0, 120), 10.05)
	return interpolator.get_interpolated_position(10.05) == Vector2(100, 100)


func test_sixty_hz_history_still_brackets_the_presentation_delay() -> Variant:
	var interpolator := _interpolator()
	for index in range(24):
		interpolator.add_server_state(Vector2(100 + index * 2, 80), Vector2(120, 0), 10.0 + index / 60.0)
	var now := 10.0 + 23.0 / 60.0
	var expected := Vector2(100 + (now - 10.0 - 0.08) * 120, 80)
	return interpolator.get_interpolated_position(now).distance_to(expected) < 0.0001


func test_extrapolation_is_time_based_capped_and_holds_through_an_outage() -> Variant:
	var sparse := _interpolator()
	var frequent := _interpolator()
	for interpolator in [sparse, frequent]:
		interpolator.add_server_state(Vector2(100, 80), Vector2(120, 0), 10.0)
		interpolator.add_server_state(Vector2(106, 80), Vector2(120, 0), 10.05)
	for frame in range(40):
		frequent.get_interpolated_position(10.13 + frame / 144.0)
	var sparse_end: Vector2 = sparse.get_interpolated_position(10.5)
	var frequent_end: Vector2 = frequent.get_interpolated_position(10.5)
	return sparse_end.distance_to(Vector2(120.4, 80)) < 0.0001 and sparse_end == frequent_end and sparse.get_interpolated_position(50.0) == sparse_end


func test_twenty_hz_packets_render_continuously_at_30_60_and_144_hz() -> Variant:
	var view := _view()
	var frame_presentation: bool = view.has_method("_render_remote_players")
	var passed_all := frame_presentation
	var actor := _actor(view)
	var interpolator: Node = view.remote_player_interpolators["20"]
	for cadence in [30, 60, 144]:
		interpolator.reset()
		var packet := 0
		var max_error := 0.0
		var frozen_frames := 0
		var previous := Vector2.ZERO
		var measured := 0
		for frame in range(cadence + 1):
			var now: float = 10.0 + float(frame) / cadence
			while 10.0 + packet * 0.05 <= now + 0.000001:
				interpolator.add_server_state(Vector2(100 + packet * 6, 80), Vector2(120, 0), 10.0 + packet * 0.05)
				# Also exercise the pre-existing packet-reception sample. In the
				# baseline this is the only point at which presentation advances.
				actor.position = interpolator.get_interpolated_position(now)
				packet += 1
			if frame_presentation: view._render_remote_players(now)
			if frame >= cadence / 4:
				var expected := Vector2(100 + (now - 10.0 - 0.08) * 120, 80)
				max_error = max(max_error, actor.position.distance_to(expected))
				if measured > 0 and actor.position == previous: frozen_frames += 1
				measured += 1
				previous = actor.position
		print("REMOTE_MOTION_SAMPLE=" + JSON.stringify({"packet_hz": 20, "render_hz": cadence, "frame_presentation": frame_presentation, "samples": measured, "max_error_px": max_error, "frozen_frames": frozen_frames}))
		passed_all = passed_all and max_error < 0.0001 and frozen_frames == 0
	return passed_all


func test_game_view_process_callback_moves_without_another_packet() -> Variant:
	var view := _view()
	var actor := _actor(view)
	var interpolator: Node = view.remote_player_interpolators["20"]
	var now := Time.get_ticks_usec() / 1000000.0
	interpolator.add_server_state(Vector2(100, 80), Vector2(120, 0), now - 0.2)
	interpolator.add_server_state(Vector2(148, 80), Vector2(120, 0), now + 0.2)
	actor.position = Vector2(-999, -999)
	view.set_process(true)
	await get_tree().process_frame
	await get_tree().process_frame
	var first: Vector2 = actor.position
	await get_tree().process_frame
	view.set_process(false)
	return first.x > 100 and first.x < 148 and actor.position.x > first.x


func test_authoritative_stationary_stop_cannot_rewind_on_the_next_frame() -> Variant:
	var view := _view()
	if not view.has_method("_render_remote_players"): return "No render callback"
	var actor := _actor(view)
	var interpolator: Node = view.remote_player_interpolators["20"]
	var now := Time.get_ticks_usec() / 1000000.0
	interpolator.add_server_state(Vector2(100, 80), Vector2(120, 0), now - 0.1)
	interpolator.add_server_state(Vector2(106, 80), Vector2(120, 0), now - 0.05)
	view.update_player("20", _state(Vector2(112, 80), Vector2.ZERO))
	view._render_remote_players(now + 0.01)
	return actor.position == Vector2(112, 80) and interpolator.state_buffer.size() == 1


func test_death_freezes_presentation_and_fresh_live_state_can_resume() -> Variant:
	var view := _view()
	if not view.has_method("_render_remote_players"): return "No render callback"
	var actor := _actor(view)
	var interpolator: Node = view.remote_player_interpolators["20"]
	interpolator.add_server_state(Vector2(100, 80), Vector2(120, 0), 10.0)
	interpolator.add_server_state(Vector2(106, 80), Vector2(120, 0), 10.05)
	actor.position = Vector2(103, 80)
	view.update_player("20", _state(Vector2(112, 80), Vector2(120, 0), true))
	view._render_remote_players(11.0)
	if actor.position != Vector2(103, 80) or not interpolator.state_buffer.is_empty(): return "Dead actor kept moving"
	view.update_player("20", _state(Vector2(200, 80), Vector2(120, 0)))
	return actor.position == Vector2(200, 80) and interpolator.state_buffer.size() == 1


func test_roster_removal_and_death_cleanup_release_interpolators() -> Variant:
	var view := _view()
	_actor(view)
	_actor(view, "30")
	var removed: Node = view.remote_player_interpolators["20"]
	var dead: Node = view.remote_player_interpolators["30"]
	view._remove_dead_player("30")
	view.update_game_state({"players": {}})
	return view.player_nodes.is_empty() and view.remote_player_interpolators.is_empty() and removed.is_queued_for_deletion() and dead.is_queued_for_deletion()
