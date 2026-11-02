extends "res://tests/bot_test_suite.gd"

## Original/synthetic event fixtures through the production GameView/renderer.
## These verify Neptune presentation, not Saturn timing or audio parity.
const Timeline = preload("res://client/explosion_event_timeline.gd")
const Renderer = preload("res://client/ui/explosion_renderer.gd")
var _viewports: Array[SubViewport] = []

class CountingBomb extends Node:
	var calls := 0
	func explode() -> void:
		calls += 1


func setup_suite() -> void: pass
func setup_test() -> void: pass
func teardown_suite() -> void: pass

func teardown_test() -> void:
	for viewport in _viewports:
		viewport.queue_free()
	_viewports.clear()
	await get_tree().process_frame


func _view() -> Node2D:
	var viewport := SubViewport.new()
	viewport.size = Vector2i(320, 224)
	_viewports.append(viewport)
	add_child(viewport)
	var view := load("res://client/game_view.tscn").instantiate() as Node2D
	view.set_script(load("res://tests/support/arena_view_fixture.gd"))
	viewport.add_child(view)
	return view


func _pattern(length: int = 4) -> Array:
	var tiles: Array = [{"grid_pos": {"x": 4, "y": 4}, "direction": "middle", "length": 0, "is_end": false}]
	for index in range(1, length + 1):
		tiles.append({"grid_pos": {"x": 4 + index, "y": 4}, "direction": "right", "length": index, "is_end": index == length})
	return tiles


func _event(id: String, start: float = 0.0, length: int = 4) -> Dictionary:
	return {"bomb_id": id, "start_time": start, "pattern": _pattern(length)}


func _compact(event: Dictionary) -> Array:
	var tiles: Array = []
	for tile in event.pattern:
		var direction := Timeline.DIRECTIONS.find(tile.direction)
		tiles.append([(tile.grid_pos.x << 8) | tile.grid_pos.y, (direction << 8) | (tile.length << 1) | int(tile.is_end)])
	return [4, 4, tiles, event.bomb_id, int(event.start_time * 100)]


func _send(view: Node, tick: int, time_msec: float, events: Array, compact := true) -> void:
	var state := {"simulation_tick": tick, "server_time": time_msec}
	if compact:
		state["e"] = []
		for event in events:
			state.e.append(_compact(event))
	else:
		state["explosions"] = events
	view.update_game_state(state)
	for node in view.explosion_nodes.values():
		node.set_physics_process(false)


func _bomb(view: Node, id: String) -> CountingBomb:
	var bomb := CountingBomb.new()
	view.bombs_container.add_child(bomb)
	view.bomb_nodes[id] = bomb
	return bomb


func test_compact_and_legacy_batches_are_additive_not_active_rosters() -> Variant:
	var view := _view()
	_send(view, 1, 0.0, [_event("first")])
	var first: Node = view.explosion_nodes.first
	_send(view, 2, 20.0, [_event("second", 0.02)], false)
	_send(view, 3, 40.0, [])
	view.update_game_state({"simulation_tick": 4, "server_time": 60.0})
	return view.explosion_nodes.size() == 2 and view.explosion_nodes.first == first and not first.is_queued_for_deletion() and first.elapsed_time == 0.0


func test_delayed_event_samples_existing_expansion_and_size_phase_immediately() -> Variant:
	var view := _view()
	_send(view, 1, 700.0, [_event("late", 0.0, 40)])
	var renderer: Node = view.explosion_nodes.late
	if not is_equal_approx(renderer.elapsed_time, 0.7) or renderer.current_length != 36 or renderer.current_size_stage != 3 or renderer.fire_nodes.size() != 36:
		return "Late event restarted expansion or size phase"
	for segment in renderer.fire_nodes.values():
		if segment._current_stage != "smaller" or segment.get_node("Sprite").texture == null:
			return "Immediate segments were configured before their native sprites were ready"
	return true


func test_late_initialization_matches_a_running_renderer_at_the_same_age() -> Variant:
	var early_view := _view()
	var late_view := _view()
	_send(early_view, 1, 0.0, [_event("same", 0.0, 20)])
	_send(late_view, 1, 310.0, [_event("same", 0.0, 20)])
	var early: Node = early_view.explosion_nodes.same
	var late: Node = late_view.explosion_nodes.same
	early._physics_process(0.31)
	return early.elapsed_time == late.elapsed_time and early.current_length == late.current_length and early.current_size_stage == late.current_size_stage and early.fire_nodes.keys() == late.fire_nodes.keys()


func test_physics_delta_controls_age_independently_of_wall_pacing() -> Variant:
	var view := _view()
	_send(view, 1, 100.0, [_event("first"), _event("second")])
	var first: Node = view.explosion_nodes.first
	var second: Node = view.explosion_nodes.second
	first._physics_process(0.21)
	OS.delay_msec(30)
	second._physics_process(0.21)
	first._physics_process(0.0)
	return first.elapsed_time == second.elapsed_time and first.current_length == second.current_length and first.current_size_stage == second.current_size_stage


func test_duplicate_delivery_keeps_renderer_age_and_dispatches_sound_once() -> Variant:
	var view := _view()
	var bomb := _bomb(view, "same")
	_send(view, 1, 100.0, [_event("same")])
	var original: Node = view.explosion_nodes.same
	original._physics_process(0.1)
	_send(view, 2, 200.0, [_event("same")])
	_send(view, 2, 200.0, [_event("same")])
	return view.explosion_nodes.same == original and is_equal_approx(original.elapsed_time, 0.2) and bomb.calls == 1


func test_self_expiry_cleans_dictionary_and_cannot_replay_sound_or_visuals() -> Variant:
	var view := _view()
	var bomb := _bomb(view, "once")
	_send(view, 1, 0.0, [_event("once")])
	var node: Node = view.explosion_nodes.once
	node._physics_process(0.81)
	await get_tree().process_frame
	if view.explosion_nodes.has("once"):
		return "Freed renderer left a stale dictionary entry"
	_send(view, 2, 100.0, [_event("once")])
	if not view.explosion_nodes.is_empty() or bomb.calls != 1:
		return "Locally expired event replayed before authoritative expiry"
	_send(view, 3, 1000.0, [_event("once")])
	return view.explosion_nodes.is_empty() and bomb.calls == 1 and view._explosion_timeline.last_rejection == "expired_event"


func test_long_pattern_lifetime_and_tombstones_follow_growth_completion() -> Variant:
	var view := _view()
	_send(view, 1, 900.0, [_event("long", 0.0, 127)])
	var node: Node = view.explosion_nodes.long
	if node.is_queued_for_deletion() or node.current_length != 46:
		return "Long pattern was treated as a fixed 0.8-second event"
	node._physics_process(1.7)
	await get_tree().process_frame
	if not view.explosion_nodes.is_empty():
		return "Completed long pattern was retained"
	_send(view, 2, 1000.0, [_event("long", 0.0, 127)])
	if not view.explosion_nodes.is_empty() or not view._explosion_timeline.seen.has("long"):
		return "Long event tombstone expired at the short-pattern deadline"
	_send(view, 3, 2600.0, [_event("long", 0.0, 127)])
	return view.explosion_nodes.is_empty() and not view._explosion_timeline.seen.has("long")


func test_lifetime_boundaries_preserve_existing_strict_short_and_long_rules() -> Variant:
	var view := _view()
	_send(view, 1, 800.0, [_event("edge")])
	var node: Node = view.explosion_nodes.edge
	if node.is_queued_for_deletion():
		return "Existing strict greater-than 0.8 boundary was changed"
	node._physics_process(0.001)
	if not node.is_queued_for_deletion():
		return "Short effect failed to expire after its boundary"
	return not Renderer.has_finished_age(2.53, 127) and Renderer.has_finished_age(2.55, 127)


func test_valid_clock_without_events_blocks_old_events_without_dropping_other_state() -> Variant:
	var view := _view()
	view.update_game_state({"simulation_tick": 2, "server_time": 200.0})
	var actor := Node2D.new()
	view.players_container.add_child(actor)
	view.player_nodes["test"] = actor
	view.update_game_state({"simulation_tick": 1, "server_time": 100.0, "e": [_compact(_event("old"))], "players": {}})
	_send(view, 3, 199.0, [_event("decreased")])
	_send(view, 2, 200.0, [_event("duplicate-header")])
	return view.explosion_nodes.is_empty() and actor.is_queued_for_deletion() and view._explosion_timeline.last_tick == 2


func test_explicit_reset_allows_reused_ids_without_old_cleanup_erasing_new_node() -> Variant:
	var view := _view()
	_send(view, 9, 100.0, [_event("reused")])
	var old: Node = view.explosion_nodes.reused
	var old_instance := old.get_instance_id()
	_send(view, 0, 0.0, [_event("reused")])
	if view.explosion_nodes.reused != old:
		return "Clock decrease implicitly reset the timeline"
	view.reset_explosion_timeline()
	_send(view, 0, 0.0, [_event("reused")])
	var replacement: Node = view.explosion_nodes.reused
	await get_tree().process_frame
	return replacement.get_instance_id() != old_instance and view.explosion_nodes.get("reused") == replacement and is_instance_valid(replacement)


func test_conflicting_replayable_identity_does_not_replace_an_active_effect() -> Variant:
	var view := _view()
	_send(view, 1, 0.0, [_event("same")])
	var first: Node = view.explosion_nodes.same
	_send(view, 2, 200.0, [_event("same", 0.1)])
	return view.explosion_nodes.same == first and view._explosion_timeline.last_rejection == "conflicting_event_identity"


func test_missing_nonfinite_boolean_and_future_clocks_never_create_effects() -> Variant:
	var clocks: Array = [{}, {"simulation_tick": true, "server_time": 0.0}, {"simulation_tick": 0, "server_time": true},
		{"simulation_tick": 0, "server_time": NAN}, {"simulation_tick": 0, "server_time": INF},
		{"simulation_tick": -1, "server_time": 0.0}, {"simulation_tick": 0, "server_time": -1.0}]
	for header in clocks:
		var view := _view()
		header["e"] = [_compact(_event("bad"))]
		view.update_game_state(header)
		if not view.explosion_nodes.is_empty() or not view._explosion_timeline.seen.is_empty():
			return "Invalid snapshot clock created an effect"
	var future := _view()
	_send(future, 0, 0.0, [_event("future", 0.01)])
	return future.explosion_nodes.is_empty() and future._explosion_timeline.last_rejection == "invalid_event_time"


func test_malformed_compact_events_fail_without_partial_nodes_or_tombstones() -> Variant:
	var view := _view()
	var valid := _compact(_event("bad"))
	var invalid: Array = [null, 1, {}, [0], [4, 4, null, "bad", 0], [4, 4, [], "bad", 0],
		[4, 4, [[0]], "bad", 0], [4, 4, [[0, true]], "bad", 0], [4, 4, [[-1, 0]], "bad", 0],
		[4, 4, [[0, 0x700]], "bad", 0], [4, 4, [[0, 0x800]], "bad", 0], [4, 4, [[0, 0]], "bad", true]]
	var tick := 0
	for entry in invalid:
		view.update_game_state({"simulation_tick": tick, "server_time": 0.0, "e": [entry]})
		tick += 1
		if not view.explosion_nodes.is_empty() or not view._explosion_timeline.seen.is_empty():
			return "Malformed compact event partially registered"
	view.update_game_state({"simulation_tick": tick, "server_time": 0.0, "e": [null, valid]})
	return view.explosion_nodes.size() == 1 and view.explosion_nodes.has("bad")


func test_malformed_legacy_event_is_validated_before_audio_or_seen_state() -> Variant:
	var view := _view()
	var bomb := _bomb(view, "bad")
	var invalid: Array = [null, {}, {"bomb_id": "", "start_time": 0.0, "pattern": _pattern()},
		{"bomb_id": "bad", "start_time": true, "pattern": _pattern()},
		{"bomb_id": "bad", "start_time": NAN, "pattern": _pattern()},
		{"bomb_id": "bad", "start_time": INF, "pattern": _pattern()},
		{"bomb_id": "bad", "start_time": 0.0, "pattern": []}]
	for field in ["grid_pos", "length", "direction", "is_end"]:
		var event := _event("bad")
		event.pattern[-1].erase(field)
		invalid.append(event)
	for override in [{"length": true}, {"length": -1}, {"length": 128}, {"direction": "unknown"}, {"is_end": 1}, {"grid_pos": {"x": true, "y": 1}}]:
		var event := _event("bad")
		event.pattern[-1].merge(override, true)
		invalid.append(event)
	var duplicate := _event("bad")
	duplicate.pattern.append(duplicate.pattern[0].duplicate(true))
	invalid.append(duplicate)
	var tick := 0
	for event in invalid:
		_send(view, tick, 0.0, [event], false)
		tick += 1
		if not view.explosion_nodes.is_empty() or not view._explosion_timeline.seen.is_empty() or bomb.calls != 0:
			return "Malformed legacy event had side effects"
	return true


func test_seen_budget_never_evicts_replayable_events_and_recovers_on_expiry() -> Variant:
	var timeline := Timeline.new()
	if not timeline.observe_snapshot(0, 0.0, {}): return "Missing initial clock"
	for index in Timeline.MAX_SEEN_EVENTS:
		if not timeline.accept_event(_event(str(index)), {}).accepted: return "Bounded fixture rejected too soon"
	if timeline.accept_event(_event("overflow"), {}).accepted or timeline.seen.size() != Timeline.MAX_SEEN_EVENTS or not timeline.seen.has("0"):
		return "Budget evicted a replayable event"
	timeline.observe_snapshot(1, 1000.0, {})
	return timeline.seen.is_empty() and timeline.accept_event(_event("new", 1.0), {}).accepted and not timeline.accept_event(_event("0"), {}).accepted


func test_large_finite_times_and_deltas_cannot_overflow_frame_conversion() -> Variant:
	var view := _view()
	_send(view, 1, 1.0e308, [_event("expired")])
	if not view.explosion_nodes.is_empty(): return "Huge old event was accepted"
	view.reset_explosion_timeline()
	_send(view, 0, 0.0, [_event("delta", 0.0, 127)])
	var node: Node = view.explosion_nodes.delta
	node._physics_process(1.0e308)
	node._physics_process(1.0e308)
	return node.is_queued_for_deletion() and Renderer.has_finished_age(1.0e308, 127)
