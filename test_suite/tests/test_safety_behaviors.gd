extends Node

# Validates safety-related behaviors: post-bomb escape commitment and no-unsafe-bomb.

const ServerPlayer = preload("res://shared/entities/server_player.gd")

func run(ctx) -> Dictionary:
	ctx.assert.clear()
	var ok_all := true
	var msgs: Array = []
	# Subtest A: Post-bomb escape commitment
	var res_a = await _test_post_bomb_escape(ctx)
	ok_all = ok_all and res_a.ok
	if not res_a.ok: msgs.append("A:"+res_a.message)
	# Subtest B: No unsafe bomb (enclosed)
	var res_b = await _test_no_unsafe_bomb(ctx)
	ok_all = ok_all and res_b.ok
	if not res_b.ok: msgs.append("B:"+res_b.message)
	var out_msg = "Safety OK"
	if not ok_all:
		out_msg = "; ".join(msgs)
	return {"ok": ok_all, "message": out_msg}

func _test_post_bomb_escape(ctx) -> Dictionary:
	var map_dict = ctx.map_factory.small_open()
	var game = await ctx.ai_spawn.make_game(map_dict)
	game.load_custom_map(map_dict)
	var ai = ctx.ai_spawn.spawn_ai(game, 0)
	await ctx.tick.step_frames(2)
	# Force a bomb placement immediately (ensure availability)
	if ai.can_place_bomb():
		ai.request_bomb_placement()
	# Check commitment on the SAME frame (GameInstance processes in _physics_process)
	# But we need to let the physics frame complete
	await get_tree().physics_frame
	var committed: int = ai.recovery_frames_remaining
	ctx.assert.assert_equal(committed, ServerPlayer.POST_BOMB_ESCAPE_DURATION, "Post-bomb escape commitment not applied")
	# Ensure AI moves away for some frames
	var start_tile = ai.get_tile_position()
	await ctx.tick.step_frames(10)
	var end_tile = ai.get_tile_position()
	ctx.assert.assert_not_equal(start_tile, end_tile, "AI did not move away after planting")
	var s = ctx.assert.summary()
	var ok = s.failed == 0
	if not ok:
		return {"ok": false, "message": str(s.failures)}
	return {"ok": true, "message": "A OK"}

func _test_no_unsafe_bomb(ctx) -> Dictionary:
	# Enclosed map around AI so no escape exists: a 5x5 room fully walled except AI center surrounded by walls
	var w = 5
	var h = 5
	var grid = []
	for y in range(h):
		var row = []
		for x in range(w):
			if x == 0 or y == 0 or x == w-1 or y == h-1:
				row.append(1)
			else:
				row.append(1) # filled walls inside too
		grid.append(row)
	# carve a single empty center for AI spawn at (2,2)
	grid[2][2] = 0
	var map_dict = {
		"grid": grid,
		"spawn_points": [Vector2(2*64+32,2*64+32)],
		"name": "unsafe_enclosed",
		"soft_slots": [],
		"metadata": {}
	}
	var game = await ctx.ai_spawn.make_game(map_dict)
	game.load_custom_map(map_dict)
	var ai = ctx.ai_spawn.spawn_ai(game, 0)
	# Disable power-up spawning to prevent accidental bombs
	game.set_meta("disable_powerup_spawn", true)
	# Observe for some frames and ensure no bomb was placed
	var bomb_count_start = game.bombs.size()
	for i in range(180):
		await ctx.tick.step_frames(1)
		# if a bomb appears, it's a failure
		if game.bombs.size() > bomb_count_start:
			ctx.assert.assert_true(false, "AI placed a bomb in unsafe enclosed tile")
			break
	var s = ctx.assert.summary()
	var ok = s.failed == 0
	var msg = "B OK"
	if not ok:
		msg = str(s.failures)
	return {"ok": ok, "message": msg}
