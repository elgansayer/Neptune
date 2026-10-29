extends "res://tests/bot_test_suite.gd"

const ROOM = preload("res://tests/support/fixture_game_instance.gd")
const BOMB = preload("res://shared/entities/ServerBomb.tscn")
const REPEATS := 8

# Each case owns/disposes actual rooms rather than the suite's usual shared room.
func setup_suite() -> void:
	pass

func teardown_suite() -> void:
	pass

func setup_test() -> void:
	pass

func teardown_test() -> void:
	pass

func _discard_room(retiring: bool) -> bool:
	seed(424242)
	var room: GameInstance = ROOM.new()
	add_child(room)
	room.set_physics_process(false)
	room.bot_manager.set_physics_process(false)
	var bomb: ServerBomb = BOMB.instantiate()
	bomb.game_instance = room
	bomb.bomb_id = "lifecycle"
	bomb.position = BotTestHelpers.tile_to_world_center(Vector2i(2, 2))
	room.bombs[bomb.bomb_id] = bomb
	room.add_child(bomb)
	bomb.set_physics_process(false)
	if retiring:
		bomb.explode()
		for step in range(bomb.explosion_range + 1):
			bomb.expand_explosion()
	var room_ref: WeakRef = weakref(room)
	var bomb_ref: WeakRef = weakref(bomb)
	room.queue_free()
	await get_tree().process_frame
	await get_tree().process_frame
	return room_ref.get_ref() == null and bomb_ref.get_ref() == null

func _measure_disposal(retiring: bool) -> Variant:
	# Warm the same actual room, map resources and measurement coroutine first.
	for index in range(2):
		if not await _discard_room(retiring): return "Warm-up did not dispose its real room/bomb"
	var before := int(Performance.get_monitor(Performance.OBJECT_COUNT))
	for index in range(REPEATS):
		if not await _discard_room(retiring): return "Actual room/bomb remained alive after teardown"
	var after := int(Performance.get_monitor(Performance.OBJECT_COUNT))
	print("BOMB_LIFECYCLE=" + JSON.stringify({"retiring": retiring, "rooms": REPEATS, "before": before, "after": after, "retained": after - before}))
	return assert_eq(after, before, "Repeated room destruction must not retain engine objects after warm-up")

func test_room_disposal_before_explosion_does_not_retain_objects() -> Variant:
	return await _measure_disposal(false)

func test_room_disposal_during_bomb_removal_does_not_retain_objects() -> Variant:
	return await _measure_disposal(true)

func test_completed_explosion_keeps_half_second_removal_delay_when_paused() -> Variant:
	var bomb: ServerBomb = BOMB.instantiate()
	add_child(bomb)
	bomb.set_physics_process(false)
	bomb.explode()
	for step in range(bomb.explosion_range + 1):
		bomb.expand_explosion()
	var original: WeakRef = weakref(bomb)
	var previous_mode := process_mode
	process_mode = Node.PROCESS_MODE_ALWAYS
	get_tree().paused = true
	await get_tree().create_timer(0.25).timeout
	var retained_until_delay: bool = original.get_ref() != null
	await get_tree().create_timer(0.4).timeout
	var removed_after_delay: bool = original.get_ref() == null
	get_tree().paused = false
	process_mode = previous_mode
	if not removed_after_delay and is_instance_valid(bomb): bomb.queue_free()
	return assert_true(retained_until_delay and removed_after_delay, "Preserve the original half-second, pause-always removal; room disposal must still cancel it")
