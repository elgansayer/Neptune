extends "res://tests/bot_test_suite.gd"

var player: ServerPlayer
var collections := 0

func setup_test() -> void:
	game_instance.match_active = false
	game_instance.set_physics_process(false)
	bot_manager.set_physics_process(false)
	await super()
	game_instance.match_active = true
	collections = 0
	game_instance.add_player(901, "EggPhysicsPlayer", BotTestHelpers.tile_to_world_center(Vector2i(5, 5)))
	player = game_instance.players[901]
	player.set_physics_process(false)

func _frames(count: int) -> void:
	for frame in range(count):
		game_instance.current_time_msec += 1000.0 / 60.0
		game_instance.simulation_tick += 1
		await get_tree().physics_frame
		await get_tree().process_frame

func _egg():
	game_instance.spawn_egg(Vector2i(5, 5))
	var egg = game_instance.eggs.values().back()
	egg.egg_collected.connect(func(value):
		collections += 1
		# An external consumer may retire the egg as soon as collection is
		# published. Hatching and pickup callbacks must not depend on its life.
		value.queue_free())
	return egg

func test_real_physics_collection_hatches_once_and_mounts_after_the_egg_is_freed() -> Variant:
	var egg = _egg()
	await _frames(6)
	if collections != 1 or is_instance_valid(egg) or not game_instance.eggs.is_empty() or game_instance.tirras.size() != 1:
		return "Actual body-entered collection must retire one egg and hatch exactly one registered mount"
	var tirra = game_instance.tirras.values()[0]
	if not is_instance_valid(tirra.get_node_or_null("PickupArea")):
		return "The hatch did not retain its real pickup collision area"
	if not player.is_flying or player._pending_tirra_mount != tirra:
		return "Pickup stopped functioning when its source egg was freed"
	player.set_physics_process(true)
	await _frames(100)
	return assert_true(player.is_mounted and player.mounted_tirra == tirra
		and tirra.get_parent() == player and tirra.get_node_or_null("PickupArea") == null,
		"The actual arc landing must defer mount reparenting and remove the pickup area safely")

func test_actor_removed_during_collection_does_not_spawn_an_orphan_mount() -> Variant:
	var egg = _egg()
	egg.egg_collected.connect(func(_value): game_instance.remove_player(901))
	await _frames(6)
	return assert_true(collections == 1 and game_instance.tirras.is_empty() and game_instance.eggs.is_empty(),
		"Deferred hatching must revalidate the weak actor reference after collection callbacks remove it")
