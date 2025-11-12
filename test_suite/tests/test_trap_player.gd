extends Node

# AI should trap a stationary dummy in a corridor and kill it with a bomb.

func run(ctx) -> Dictionary:
	ctx.assert.clear()
	var map_dict = ctx.map_factory.trap_corridor()
	var game = await ctx.ai_spawn.make_game(map_dict)
	game.load_custom_map(map_dict)
	var ai = ctx.ai_spawn.spawn_ai(game, 1) # aggressive
	# Boost bomb tendency deterministically if possible
	if ai.has("controller") and ai.controller and ai.controller.has("personality_weights"):
		ai.controller.personality_weights["bomb_frequency"] = 1.0
		ai.controller.personality_weights["aggression"] = 1000.0
	# Spawn dummy ahead in corridor (second spawn)
	var dummy = ctx.ai_spawn.spawn_dummy_player(game, 1)
	# Ensure both are in scene tree
	await ctx.tick.step_frames(5)
	if not is_instance_valid(dummy) or not is_instance_valid(ai):
		ctx.assert.assert_true(false, "Failed to spawn AI or dummy")
		return {"ok": false, "message": "Spawn failure"}
	var dummy_killed = false
	var ai_alive = true
	var max_frames = 600
	for i in range(max_frames):
		await ctx.tick.step_frames(1)
		if dummy.is_dead:
			dummy_killed = true
			break
		if ai.is_dead:
			ai_alive = false
			break
	ctx.assert.assert_true(dummy_killed, "Dummy was not killed (trap failed)")
	ctx.assert.assert_true(ai_alive, "AI died during trap scenario")
	var summary = ctx.assert.summary()
	var ok = summary.failed == 0
	var msg = "Trap succeeded"
	if not ok:
		msg = str(summary.failures)
	return {"ok": ok, "message": msg}
