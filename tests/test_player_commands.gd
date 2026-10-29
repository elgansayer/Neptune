extends "res://tests/support/player_command_fixture.gd"

func test_finite_in_range_control_retains_the_intended_axes() -> Variant:
	actor.set_input(0.5, -1.0)
	return assert_eq(actor.input_direction, Vector2(0.5, -1.0), "Valid analog/cardinal intent must remain unchanged")

func test_direct_nonfinite_and_out_of_range_movement_cannot_reach_physics() -> Variant:
	for value in [NAN, INF, -INF, 1.01, -2.0]:
		actor.input_direction = Vector2.ZERO
		actor.set_input(value, 0.0)
		if actor.input_direction != Vector2.ZERO:
			return "Direct movement admitted a nonfinite or out-of-range axis"
	return true

func test_invalid_packet_cannot_move_then_place_a_bomb() -> Variant:
	var before := snapshot()
	game_instance.handle_player_input(actor.peer_id, {"input_x": 2.0, "place_bomb": true})
	return assert_eq(snapshot(), before, "Packet validation must precede movement and ability effects")

func test_unknown_packet_fields_cannot_request_an_action() -> Variant:
	var before := snapshot()
	game_instance.handle_player_input(actor.peer_id, {"position": Vector2.ZERO, "place_bomb": true})
	return assert_eq(snapshot(), before, "Unsupported packet fields must reject the complete packet")

func test_dead_player_cannot_pick_up_a_real_bomb() -> Variant:
	actor.has_power_glove = true
	var bomb := own_bomb()
	actor.is_dead = true
	var before := snapshot()
	if actor.try_pickup_bomb(bomb) or snapshot() != before:
		return "Dead actor changed the real bomb to CARRIED"
	return true

func test_inactive_player_cannot_pick_up_a_real_bomb() -> Variant:
	actor.has_power_glove = true
	var bomb := own_bomb()
	game_instance.match_active = false
	var before := snapshot()
	if actor.try_pickup_bomb(bomb) or snapshot() != before:
		return "Inactive actor changed the real bomb to CARRIED"
	return true

func test_dead_player_cannot_throw_a_real_carried_bomb() -> Variant:
	actor.has_power_glove = true
	var bomb := own_bomb()
	if not actor.try_pickup_bomb(bomb):
		return "Living pickup control did not establish a real carried bomb"
	actor.is_dead = true
	var before := snapshot()
	return assert_true(not actor.throw_carried_bomb() and snapshot() == before, "Dead actor must not launch its carried bomb")

func test_inactive_actor_does_not_keep_moving_on_actual_physics_callbacks() -> Variant:
	actor.set_input(1.0, 0.0)
	var before := actor.position
	game_instance.match_active = false
	actor.set_physics_process(true)
	for step in range(6):
		await get_tree().physics_frame
	await get_tree().process_frame
	actor.set_physics_process(false)
	return assert_eq(actor.position, before, "Countdown/ended actors must freeze normal movement")

func test_malformed_packet_types_and_edges_are_atomic() -> Variant:
	var packets: Array[Dictionary] = []
	for value in [null, true, "1", [], {}, Vector2.RIGHT, NAN, INF, -2.0]:
		packets.append({"input_x": value, "place_bomb": true})
	for value in [null, 0, 1, "false", []]:
		packets.append({"input_x": 0.5, "action_pressed": value, "place_bomb": true})
	packets.append({"input_x": 0.5, "speed": 999, "place_bomb": true})
	actor.active_virus = ServerPlayer.VirusType.LEISURELY_FUSE
	for packet in packets:
		var before := snapshot()
		seed(789)
		var expected := randf()
		seed(789)
		var outcome: Dictionary = game_instance.handle_player_input(actor.peer_id, packet)
		if outcome.accepted or snapshot() != before or randf() != expected:
			return "Malformed complete packet mutated movement/action/world/RNG"
	return true

func test_unknown_commands_fields_and_actors_return_reasons() -> Variant:
	var before := snapshot()
	for command in [{}, {"action": "teleport"}, {"action": "move", "x": 0, "position": Vector2.ZERO}, {"action": "throw_bomb", "speed": 10}]:
		var outcome: Dictionary = game_instance.submit_player_command(actor.peer_id, command)
		if outcome.accepted or outcome.reason not in ["unknown_action", "unknown_field"] or snapshot() != before:
			return "Unknown action/schema failed to reject before mutation"
	var unknown: Dictionary = game_instance.submit_player_command(999, {"action": "move", "x": 1})
	actor.game_instance = null
	var foreign: Dictionary = game_instance.submit_player_command(actor.peer_id, {"action": "move", "x": 1})
	actor.game_instance = game_instance
	return assert_true(unknown.reason == "unknown_player" and foreign.reason == "foreign_player" and snapshot() == before, "Authority membership must be identical for every command")

func test_neutral_cleanup_is_allowed_but_dead_inactive_actions_are_not() -> Variant:
	actor.input_direction = Vector2.RIGHT
	actor.action_button_pressed = true
	actor.is_dead = true
	game_instance.match_active = false
	var moved: Dictionary = actor.set_input(0, 0)
	var released: Dictionary = actor.request_action_release()
	if not moved.accepted or not released.accepted or actor.input_direction != Vector2.ZERO or actor.action_button_pressed:
		return "Neutral cleanup became impossible after death/end"
	for command in [{"action": "move", "x": 1}, {"action": "pickup_bomb", "bomb_id": "0"}, {"action": "throw_bomb"}, {"action": "mount_action"}, {"action": "detonate_remote"}]:
		var before := snapshot()
		var outcome: Dictionary = game_instance.submit_player_command(actor.peer_id, command)
		if outcome.accepted or outcome.reason != "match_inactive" or snapshot() != before:
			return "Inactive command bypassed common authority guard"
	return true

func test_ability_requests_without_inventory_do_not_mutate() -> Variant:
	for command in [{"action": "pickup_bomb", "bomb_id": "0"}, {"action": "throw_bomb"}, {"action": "mount_action"}, {"action": "detonate_remote"}, {"action": "action_press"}]:
		var before := snapshot()
		var outcome: Dictionary = game_instance.submit_player_command(actor.peer_id, command)
		if outcome.accepted or outcome.reason != "ability_unavailable" or snapshot() != before:
			return "An unavailable ability produced effects"
	return true

func test_pickup_requires_a_tracked_local_bomb_on_the_actor_tile() -> Variant:
	actor.has_power_glove = true
	var bomb := own_bomb()
	var foreign: ServerBomb = game_instance.ServerBombScene.instantiate()
	foreign.bomb_id = bomb.bomb_id
	var before := snapshot()
	var accepted: bool = actor.try_pickup_bomb(foreign)
	foreign.free()
	if accepted or actor.last_command_result.reason != "foreign_bomb" or snapshot() != before:
		return "A foreign object with a matching ID selected a local bomb"
	actor.position = BotTestHelpers.tile_to_world_center(Vector2i(8, 6))
	var off_tile: Dictionary = game_instance.submit_player_command(actor.peer_id, {"action": "pickup_bomb", "bomb_id": bomb.bomb_id})
	if off_tile.accepted or off_tile.reason != "not_on_bomb":
		return "Pickup reached across tiles"
	for invalid in [null, 0, [], "", "x".repeat(65)]:
		var outcome: Dictionary = game_instance.submit_player_command(actor.peer_id, {"action": "pickup_bomb", "bomb_id": invalid})
		if outcome.accepted or outcome.reason != "invalid_bomb_id":
			return "Malformed bomb ID was accepted"
	return true

func test_real_pickup_and_throw_use_the_original_state_machine() -> Variant:
	actor.has_power_glove = true
	var bomb := own_bomb()
	if not actor.try_pickup_bomb(bomb) or bomb.bomb_state != ServerBomb.BombState.CARRIED or bomb.carrying_player != actor:
		return "Accepted pickup did not enter the production CARRIED state"
	actor.last_move_direction = Vector2.RIGHT
	if not actor.throw_carried_bomb() or bomb.bomb_state != ServerBomb.BombState.THROWN or actor.is_carrying_bomb():
		return "Accepted throw did not enter the production THROWN state"
	return assert_true(bomb.throw_direction == Vector2.RIGHT and actor.last_command_result.reason == "thrown" and bomb.fuse_time == 3.0, "Validated throw must preserve actual direction and fuse")

func test_wrong_carrier_and_invalid_facing_cannot_throw() -> Variant:
	actor.has_power_glove = true
	var bomb := own_bomb()
	if not actor.try_pickup_bomb(bomb):
		return "Pickup control failed"
	bomb.carrying_player = game_instance
	var before := snapshot()
	if actor.throw_carried_bomb() or actor.last_command_result.reason != "not_carrier" or snapshot() != before:
		return "Noncarrier launched a carried bomb"
	bomb.carrying_player = actor
	actor.last_move_direction = Vector2(NAN, 0)
	before = snapshot()
	return assert_true(not actor.throw_carried_bomb() and actor.last_command_result.reason == "invalid_direction" and snapshot() == before, "Invalid throw direction must not reach the trajectory engine")

func test_glove_space_button_and_dual_edges_perform_only_one_action() -> Variant:
	actor.has_power_glove = true
	var placed: Dictionary = game_instance.handle_player_input(actor.peer_id, {"place_bomb": true})
	if not placed.accepted or placed.reason != "placed" or game_instance.bombs.size() != 1:
		return "The production Space/glove control failed to place"
	var picked: Dictionary = game_instance.handle_player_input(actor.peer_id, {"place_bomb": true, "action_pressed": true})
	if not picked.accepted or picked.reason != "picked_up" or picked.actions.size() != 1 or not actor.is_carrying_bomb():
		return "Both glove edges performed more than one action or failed to pick up"
	var thrown: Dictionary = game_instance.handle_player_input(actor.peer_id, {"place_bomb": true})
	return assert_true(thrown.accepted and thrown.reason == "thrown" and not actor.is_carrying_bomb(), "The production Space/glove control failed to throw")

func _mount():
	# Production controller with original generated solid-colour animation frames.
	# The fixture imports no extracted character artwork.
	var controller = load("res://pack projects/tirra/blue/controller.gd").new()
	var sprite := AnimatedSprite2D.new()
	sprite.name = "baby"
	sprite.sprite_frames = SpriteFrames.new()
	var image := Image.create(1, 1, false, Image.FORMAT_RGBA8)
	image.fill(Color.WHITE)
	for name in ["down_idle", "down_kick"]:
		sprite.sprite_frames.add_animation(name)
		sprite.sprite_frames.add_frame(name, ImageTexture.create_from_image(image))
	sprite.animation = "down_idle"
	controller.add_child(sprite)
	actor.add_child(controller)
	actor.mounted_tirra = controller
	actor.is_mounted = true
	actor.last_move_direction = Vector2.DOWN
	return controller

func test_real_mounted_action_and_unchanged_cooldown() -> Variant:
	var mount = _mount()
	var first: Dictionary = actor.trigger_tirra_action()
	if not first.accepted or first.reason != "mount_started" or actor.tirra_action_cooldown != 0.5:
		return "Actual mounted controller did not start with its unchanged half-second cooldown"
	var before := snapshot()
	var second: Dictionary = actor.trigger_tirra_action()
	if second.accepted or second.reason != "cooldown" or snapshot() != before:
		return "Mounted action bypassed cooldown"
	actor.tirra_action_cooldown = 0.0
	actor.is_dead = true
	var dead: Dictionary = actor.trigger_tirra_action()
	return assert_true(not dead.accepted and dead.reason == "dead_player" and is_instance_valid(mount), "Dead actor must not start mounted actions")

func test_packet_reports_partial_actions_without_hiding_rejection() -> Variant:
	_mount()
	actor.tirra_action_cooldown = 0.5
	var outcome: Dictionary = game_instance.handle_player_input(actor.peer_id, {"input_x": 0.5, "action_pressed": true, "place_bomb": true})
	return assert_true(not outcome.accepted and outcome.reason == "cooldown" and outcome.movement.accepted and outcome.actions.size() == 2 and outcome.actions[1].accepted and game_instance.bombs.size() == 1, "Distinct valid frame actions need truthful partial outcomes")

func test_owned_remote_detonation_chooses_oldest_and_preserves_other_bombs() -> Variant:
	await game_instance.add_player(-602, "OtherRemoteFixture", BotTestHelpers.tile_to_world_center(Vector2i(1, 1)), false)
	var other: ServerPlayer = game_instance.players[-602]
	other.set_physics_process(false)
	other.bomb_type = ServerBomb.BOMB_TYPE_REMOTE
	var other_result: Dictionary = game_instance.place_bomb(other)
	var other_bomb: ServerBomb = game_instance.bombs[other_result.bomb_ids[0]]
	other_bomb.set_physics_process(false)
	actor.bomb_type = ServerBomb.BOMB_TYPE_REMOTE
	actor.max_bombs = 2
	var first := own_bomb(Vector2i(3, 3))
	var second := own_bomb(Vector2i(11, 3))
	actor.position = BotTestHelpers.tile_to_world_center(Vector2i(7, 6))
	var outcome: Dictionary = game_instance.submit_player_command(actor.peer_id, {"action": "detonate_remote"})
	var correct: bool = outcome.accepted and outcome.bomb_ids == [first.bomb_id] and first.has_exploded and not second.has_exploded and actor.bombs_placed == 1
	first.set_physics_process(true)
	# Let the actual asynchronous expansion/removal finish before fixture teardown.
	for step in range(90):
		if not is_instance_valid(first):
			break
		await get_tree().physics_frame
	return assert_true(correct and not is_instance_valid(first) and is_instance_valid(second) and not second.has_exploded and not other_bomb.has_exploded and actor.bombs_placed == 1, "Remote command must select the actual oldest owned remote, preserve unrelated bombs and drain its real expansion")

func test_buffered_input_cannot_bypass_packet_or_movement_validation() -> Variant:
	actor.initialize_input_buffer()
	var rejected: Dictionary = actor.queue_input({"input_x": NAN, "place_bomb": true})
	if rejected.accepted or actor.input_buffer.size() != 0:
		return "Malformed packet entered the input buffer"
	var packet := {"input_x": 0.5}
	var buffered: Dictionary = actor.queue_input(packet)
	packet.input_x = NAN
	if not buffered.accepted or actor.input_buffer.peek_latest().input_x != 0.5:
		return "Buffered input aliases caller mutation"
	actor.is_bot = false
	var board = ClassDB.instantiate("Blackboard")
	board.set_var("player", actor)
	board.set_var("input_buffer", actor.input_buffer)
	var task = preload("res://ai/tasks/actions/bt_update_input_from_buffer.gd").new()
	task.initialize(actor, board, get_tree().current_scene)
	if task.execute(0.02) != ClassDB.class_get_integer_constant("BT", "SUCCESS") or actor.input_direction != Vector2(0.5, 0):
		return "Valid buffered native movement failed"
	actor.input_buffer.push_input({"input_x": INF, "action_pressed": true})
	task.abort()
	var before := snapshot()
	if task.execute(0.02) != ClassDB.class_get_integer_constant("BT", "FAILURE") or snapshot() != before or board.get_var("has_input"):
		return "Direct buffer injection bypassed native revalidation"
	return true

func test_diagonal_intent_is_still_cardinal_at_real_runtime_speed() -> Variant:
	var outcome: Dictionary = actor.set_input(1, 1)
	if not outcome.accepted or actor.get_4way_input() != Vector2.DOWN:
		return "Legal diagonal key combinations changed the existing cardinal tie rule"
	var before := actor.position
	actor.set_physics_process(true)
	for step in range(6):
		await get_tree().physics_frame
	await get_tree().process_frame
	actor.set_physics_process(false)
	return assert_true(is_zero_approx(actor.position.x - before.x) and actor.position.y > before.y and actor.velocity.length() <= GameConfig.BASE_SPEED, "Actual physics must not grant a diagonal speed boost")

func test_human_and_native_move_pickup_throw_trace_matches() -> Variant:
	await game_instance.add_player(-602, "HumanActionFixture", BotTestHelpers.tile_to_world_center(Vector2i(4, 4)), false)
	var human: ServerPlayer = game_instance.players[-602]
	human.set_physics_process(false)
	human.has_power_glove = true
	actor.has_power_glove = true
	var trace := []
	for expected in ["placed", "picked_up", "thrown"]:
		var human_result: Dictionary = game_instance.handle_player_input(human.peer_id, {"input_x": 0.5, "place_bomb": true})
		var moved: Dictionary = actor.set_input(0.5, 0)
		var bot_result: Dictionary
		if expected == "placed":
			bot_result = actor.request_action_press()
		elif expected == "picked_up":
			var bomb: ServerBomb = game_instance.bombs.values().filter(func(b): return b.owner_id == actor.player_id)[0]
			actor.try_pickup_bomb(bomb)
			bot_result = actor.last_command_result
		else:
			actor.throw_carried_bomb()
			bot_result = actor.last_command_result
		var a := [human_result.accepted, human_result.reason, human_result.bomb_ids.size(), human.bombs_placed, human.is_carrying_bomb(), human.input_direction]
		var b := [bot_result.accepted, bot_result.reason, bot_result.bomb_ids.size(), actor.bombs_placed, actor.is_carrying_bomb(), actor.input_direction]
		if not moved.accepted or a != b or human_result.reason != expected:
			return "Human/native real action trace differs at %s: %s / %s" % [expected, str(a), str(b)]
		trace.append([human_result.accepted, human_result.reason, human.bombs_placed, human.is_carrying_bomb()])
	print("PLAYER_COMMAND_EQUIVALENCE_TRACE=", JSON.stringify(trace))
	return true

func test_unregistered_actor_helper_cannot_impersonate_an_existing_peer() -> Variant:
	var impostor := ServerPlayer.new()
	impostor.peer_id = actor.peer_id
	impostor.game_instance = game_instance
	var before := snapshot()
	var outcome: Dictionary = impostor.set_input(1, 0)
	impostor.free()
	return assert_true(not outcome.accepted and outcome.reason == "unknown_player" and snapshot() == before, "Actor helper identity must match the authority roster, not just its supplied peer ID")

func test_real_same_tick_fast_tap_performs_once_and_releases() -> Variant:
	actor.has_power_glove = true
	Input.action_press("player_action")
	Input.action_release("player_action")
	var packet := {"action_pressed": Input.is_action_just_pressed("player_action"), "action_released": Input.is_action_just_released("player_action")}
	if not packet.action_pressed or not packet.action_released:
		return "Real Input fixture did not produce its documented same-tick press/release"
	var outcome: Dictionary = game_instance.handle_player_input(actor.peer_id, packet)
	return assert_true(outcome.accepted and game_instance.bombs.size() == 1 and outcome.actions.size() == 2 and outcome.actions[0].reason == "placed" and outcome.actions[1].reason == "released" and not actor.action_button_pressed, "A legitimate fast tap must act once and leave the button released")
