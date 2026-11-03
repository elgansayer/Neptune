extends "res://tests/bot_test_suite.gd"

## Short real-physics matches prove liveness, not held-out competitive quality.
## Timings include observation capture and production tree updates together.
const MATCH_MSEC := 8000.0
const ILLEGAL_REFUSALS := ["unknown_action", "unknown_field", "invalid_movement", "invalid_position", "outside_map", "foreign_player", "unknown_player", "invalid_direction"]
const POLICY_SOURCES := [
	"res://game_instance.gd", "res://main_server.gd", "res://shared/game_config.gd",
	"res://shared/constants.gd", "res://shared/player_commands.gd",
	"res://shared/rooms/spawn_reservations.gd", "res://shared/runtime_config.gd",
	"res://shared/simulation_state_publisher.gd",
]
const POLICY_DIRECTORIES := ["res://ai", "res://shared/ai", "res://shared/entities", "res://shared/observations"]

func setup_suite() -> void:
	pass # Each case creates its own unmodified map and fresh authority.

func setup_test() -> void:
	pass

func teardown_test() -> void:
	if is_instance_valid(game_instance):
		game_instance.queue_free()
	await get_tree().process_frame
	await get_tree().process_frame

func teardown_suite() -> void:
	pass

func test_four_bots_play_a_seeded_standard_map() -> Variant:
	return await _play("res://maps/neptune_standard.json", 4, 46271)

func test_twelve_bots_play_a_seeded_capacity_map() -> Variant:
	return await _play("res://maps/neptune_twelve.json", 12, 81439)

func _play(map_path: String, count: int, match_seed: int) -> Variant:
	var source_hashes := _source_hashes()
	game_instance = preload("res://tests/support/profile_bot_game.gd").new()
	game_instance.game_id = "bot-liveness-%d-%d" % [count, match_seed]
	game_instance.countdown_time = 0.0
	game_instance.room_map_path = map_path
	game_instance.room_capacity_request = {"seats": count, "preset_limit": count}
	game_instance.room_bot_fill_request = {"target": count, "personality": "BALANCED"}
	game_instance.bot_policy_seed = match_seed
	game_instance.spawn_seed = match_seed
	add_child(game_instance)
	await get_tree().process_frame
	seed(match_seed) # Fixed JSON map; seed actual drops after authority setup randomizes.
	if not game_instance.room_setup_result.accepted: return "Live match authority failed setup: " + str(game_instance.room_setup_result)
	var first: Dictionary = game_instance.spawn_bot("BALANCED")
	if not first.accepted or not game_instance.start_room_countdown().accepted:
		return "Live match could not admit its first actual bot and start countdown"
	for frame in range(180):
		if game_instance.match_active: break
		await get_tree().physics_frame
		await get_tree().process_frame
	if not game_instance.match_active or game_instance.players.size() != count:
		return "Live countdown did not provision and activate the complete roster"
	bot_manager = game_instance.bot_manager
	var state: Dictionary = game_instance.get_room_capacity()
	var subjects: Dictionary = {}
	for id in game_instance.players:
		var actor = game_instance.players[id]
		if not actor.is_bot or actor.max_bombs != 1 or actor.bomb_range != 1 or actor.skate_count != 0 or actor.has_bomb_kicker or actor.has_power_glove:
			return "Live evaluation must begin with ordinary human-equivalent inventory"
		if not is_instance_valid(bot_manager.get_bot_controller(id)):
			return "Live roster lacks a real production controller"
		var cell: Vector2i = actor.get_tile_position()
		subjects[str(id)] = {"position": actor.position, "tiles": {str(cell): true}, "history": [cell], "travel_pixels": 0.0, "alive_msec": 0.0, "idle_msec": 0.0, "aba_transitions": 0}
	var start: float = game_instance.get_simulation_time_msec()
	var previous_time := start
	var observed_frames := 0
	for frame in range(900):
		if not game_instance.match_active or game_instance.get_simulation_time_msec() - start >= MATCH_MSEC: break
		await get_tree().physics_frame
		await get_tree().process_frame
		var now: float = game_instance.get_simulation_time_msec()
		var dt := maxf(0.0, now - previous_time)
		previous_time = now
		observed_frames += 1
		for id in game_instance.players:
			var actor = game_instance.players[id]
			var sample: Dictionary = subjects[str(id)]
			if actor.is_dead: continue
			sample.alive_msec += dt
			var distance: float = actor.position.distance_to(sample.position)
			sample.travel_pixels += distance
			if distance < 0.01: sample.idle_msec += dt
			sample.position = actor.position
			var cell: Vector2i = actor.get_tile_position()
			sample.tiles[str(cell)] = true
			var history: Array = sample.history
			if history.back() != cell:
				if history.size() >= 2 and history[-2] == cell: sample.aba_transitions += 1
				history.append(cell)
				if history.size() > 3: history.pop_front()
	var moved := 0
	var totals := {"alive_msec": 0.0, "idle_msec": 0.0, "travel_tiles": 0.0, "aba_transitions": 0}
	var roster := []
	for identity in subjects:
		var sample: Dictionary = subjects[identity]
		if sample.tiles.size() >= 2: moved += 1
		totals.alive_msec += sample.alive_msec
		totals.idle_msec += sample.idle_msec
		totals.travel_tiles += sample.travel_pixels / GameConfig.TILE_SIZE
		totals.aba_transitions += sample.aba_transitions
		roster.append({"peer_id": identity, "type": "bot", "personality": "BALANCED", "unique_tiles": sample.tiles.size(), "travel_tiles": sample.travel_pixels / GameConfig.TILE_SIZE, "alive_msec": sample.alive_msec, "idle_msec": sample.idle_msec, "aba_transitions": sample.aba_transitions, "commands": game_instance.participant_commands.get(identity, {})})
	var timings: Array = bot_manager.update_cost_usec.duplicate()
	timings.sort()
	var causal: Dictionary = game_instance.get_elimination_event_state()
	var report := {"schema": 1, "purpose": "short-native-liveness-not-policy-promotion", "engine": Engine.get_version_info().string, "policy": state.bot_policy, "policy_seed": str(match_seed), "gameplay_seed": str(match_seed), "map": map_path, "map_sha256": FileAccess.get_sha256(map_path), "policy_sources": source_hashes, "policy_sources_sha256": JSON.stringify(source_hashes).sha256_text(), "rules": {"tile_size": GameConfig.TILE_SIZE, "physics_hz": Engine.physics_ticks_per_second, "fuse_seconds": GameConfig.BOMB_TIMER, "flame_seconds": GameConfig.EXPLOSION_DURATION}, "participants": count, "roster": roster, "duration_msec": game_instance.get_simulation_time_msec() - start, "physics_frames_observed": observed_frames, "bots_that_changed_tile": moved, "totals": totals, "bombs_created": game_instance.next_bomb_id, "accepted_commands": game_instance.accepted_commands.duplicate(true), "refused_commands": game_instance.refused_commands.duplicate(true), "eliminations": causal, "round_result": game_instance.get_round_result(), "manager_cost_usec": {"samples": timings.size(), "p50": _percentile(timings, 0.50), "p95": _percentile(timings, 0.95), "p99": _percentile(timings, 0.99), "max": timings.back() if not timings.is_empty() else 0}}
	var stages := {}
	for stage in bot_manager.profile_stage_samples:
		var samples: Array = bot_manager.profile_stage_samples[stage].duplicate()
		samples.sort()
		stages[stage] = {"samples": samples.size(), "p50": _percentile(samples, 0.50), "p95": _percentile(samples, 0.95), "p99": _percentile(samples, 0.99), "max": samples.back() if not samples.is_empty() else 0}
	report["manager_stages_usec"] = stages
	print("BOT_MATCH_EVIDENCE=" + JSON.stringify(report))
	if source_hashes != _source_hashes(): return "Selected policy sources changed during the actual match"
	if observed_frames < 120 or timings.size() < 120: return "Live evaluation did not execute enough actual simulation/controller callbacks"
	if moved < count: return "Live room has %d/%d bots that never changed tile" % [count - moved, count]
	if game_instance.next_bomb_id <= 0: return "Live room moved but no bot ever created an actual bomb"
	if causal.discarded != 0: return "Elimination evidence was truncated"
	for key in game_instance.refused_commands:
		for reason in ILLEGAL_REFUSALS:
			if key.ends_with(":" + reason): return "Live policy submitted illegal command: " + key
	return true

func _percentile(values: Array, quantile: float) -> int:
	return int(values[clampi(ceili(values.size() * quantile) - 1, 0, values.size() - 1)]) if not values.is_empty() else 0

func _source_hashes() -> Dictionary:
	var sources: Array[String] = []
	for path in POLICY_SOURCES: sources.append(path)
	for directory in POLICY_DIRECTORIES: _append_sources(directory, sources)
	sources.sort()
	var hashes := {}
	for source in sources: hashes[source] = FileAccess.get_sha256(source)
	return hashes

func _append_sources(path: String, sources: Array[String]) -> void:
	var directory := DirAccess.open(path)
	if directory == null:
		push_error("Missing evaluated policy source directory: " + path)
		return
	for child in directory.get_directories():
		if not child.begins_with(".") and not directory.is_link(child):
			_append_sources(path.path_join(child), sources)
	for child in directory.get_files():
		if child.get_extension() in ["gd", "tres", "tscn"] and not directory.is_link(child):
			sources.append(path.path_join(child))
