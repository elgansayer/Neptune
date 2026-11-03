extends "res://tests/bot_test_suite.gd"

const Record = preload("res://shared/observations/record.gd")

func setup_test() -> void:
	game_instance.set_physics_process(false)
	bot_manager.set_physics_process(false)
	await super()
	game_instance.match_active = true

func _views() -> Array:
	await spawn_bot_at(Vector2i(3, 3))
	var first_id: int = bot_player.peer_id
	bot_player.set_physics_process(false)
	await spawn_bot_at(Vector2i(9, 9))
	bot_player.set_physics_process(false)
	bot_manager.set_physics_process(false)
	bot_manager.refresh_public_observations(true)
	return [bot_manager._observation_views[first_id], bot_manager._observation_views[bot_player.peer_id]]

func test_source_payloads_are_frozen_once_and_shared_between_isolated_records() -> Variant:
	var views: Array = await _views()
	var frame: Dictionary = bot_manager.observation_source.frame()
	var id: int = views[0].own_peer_id
	var first = views[0].players[id]
	var second = views[1].players[id]
	if first == second or not frame.is_read_only() or not frame.terrain.is_read_only() or not frame.terrain[0].is_read_only():
		return "Frames must be immutable while per-view record objects remain independent"
	if not first._data.is_read_only() or not first._data.position.is_read_only() or not is_same(first._data, second._data):
		return "The source's frozen player payload was copied per viewer instead of safely shared"
	var replacement: Dictionary = first.public_data()
	replacement.username = "LocalRecordChange"
	first.update(replacement)
	return assert_true(second.player_name != "LocalRecordChange"
		and frame.players[str(id)].username != "LocalRecordChange",
		"Reassigning one viewer's record cannot modify another viewer or the shared frame")

func test_public_frame_and_record_compound_getters_remain_writable_detached_copies() -> Variant:
	var views: Array = await _views()
	var id: int = views[0].own_peer_id
	var actor: ServerPlayer = game_instance.players[id]
	var placed: Dictionary = actor.request_bomb_placement()
	if not placed.accepted: return "Mutable-export fixture could not place its actual bomb"
	var bomb_id: String = placed.bomb_ids[0]
	game_instance.bombs[bomb_id].set_physics_process(false)
	bot_manager.refresh_public_observations(true)
	var snapshot: Dictionary = views[0].public_snapshot()
	var record = views[0].bombs[bomb_id]
	var other = views[1].bombs[bomb_id]
	var overlaps: Array = record.get("overlap_exemptions")
	var raw: Dictionary = record.public_data()
	if snapshot.is_read_only() or snapshot.terrain.is_read_only() or overlaps.is_read_only() or raw.position.is_read_only():
		return "Public copies accidentally inherited internal read-only flags"
	var original: Dictionary = views[1].public_snapshot()
	overlaps.append(777777)
	raw.position[0] = -12345.0
	snapshot.terrain[3][3] = 99
	snapshot.bombs[bomb_id].overlap_exemptions.clear()
	return assert_true(views[1].public_snapshot() == original
		and not other.get("overlap_exemptions").has(777777)
		and game_instance.game_map[3][3] == 0 and actor.position.x >= 0.0,
		"A public nested mutation reached another policy view or authority state")

func test_ordinary_record_updates_still_copy_mutable_nested_inputs() -> Variant:
	var position := [24.0, 24.0]
	var input := {"position": position, "extra": {"nested": [1, 2]}}
	input.make_read_only() # A frozen outer container alone is not deep immutability.
	var record = Record.new()
	record.update(input)
	position[0] = -1000.0
	input.extra.nested[0] = 99
	var exported: Dictionary = record.get("extra")
	exported.nested[1] = 88
	return assert_true(record.position == Vector2(24.0, 24.0)
		and record.public_data().extra.nested == [1, 2],
		"Ordinary record inputs and compound getters must retain their copy boundaries")

func test_refresh_keeps_own_actor_current_without_eager_opponent_group_work() -> Variant:
	var views: Array = await _views()
	var view = views[0]
	var source = bot_manager.observation_source
	var opponent_id: int = views[1].own_peer_id
	var own_id: int = view.own_peer_id
	var previous_group_version: int = view._model_versions.players
	game_instance.players[own_id].position += Vector2(2, 0)
	game_instance.players[opponent_id].position += Vector2(0, 2)
	game_instance.invalidate_public_observation()
	view.refresh()
	if view.own_actor.position != game_instance.players[own_id].position or view._model_versions.players != previous_group_version:
		return "Refreshing the motor view failed to update own actor lazily"
	var opponents: Dictionary = view.players
	return assert_true(opponents[opponent_id].position == game_instance.players[opponent_id].position
		and view._model_versions.players == source.version,
		"First group query must materialize this exact current observation revision")

func test_lazy_groups_refresh_same_tick_commands_and_remove_departed_records() -> Variant:
	var views: Array = await _views()
	var view = views[0]
	var actor: ServerPlayer = game_instance.players[view.own_peer_id]
	var before: Dictionary = view.bombs
	if not before.is_empty(): return "Lazy-group fixture begins with unexpected bombs"
	var initial_tick: int = game_instance.simulation_tick
	var placed: Dictionary = actor.request_bomb_placement()
	if not placed.accepted: return "Lazy-group fixture could not place an actual bomb"
	var bomb_id: String = placed.bomb_ids[0]
	game_instance.bombs[bomb_id].set_physics_process(false)
	var current: Dictionary = view.bombs
	if game_instance.simulation_tick != initial_tick or not current.has(bomb_id) or not before.is_empty():
		return "Accepted same-tick commands did not refresh lazy groups or mutated prior dictionary exports"
	var opponent_id: int = views[1].own_peer_id
	var prior_players: Dictionary = view.players
	game_instance.remove_player(opponent_id)
	var remaining: Dictionary = view.players
	return assert_true(prior_players.has(opponent_id) and not remaining.has(opponent_id)
		and remaining.has(view.own_peer_id),
		"A lazy player query retained departed actors or altered earlier group exports")
