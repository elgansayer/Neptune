extends Node

# AI should place a bomb and destroy the soft block at (3,2) in soft_block_line map.

func run(ctx) -> Dictionary:
	ctx.assert.clear()
	var map_dict = ctx.map_factory.soft_block_line()
	var game = await ctx.ai_spawn.make_game(map_dict)
	game.load_custom_map(map_dict)
	var ai = ctx.ai_spawn.spawn_ai(game, 0)
	var soft_tile := Vector2i(3,2)
	# Place a power-up behind the soft block to motivate bombing
	var target_tile := Vector2i(4,2)
	game.spawn_powerup(target_tile)
	
	# Give AI a few frames to initialize
	await ctx.tick.step_frames(5)
	
	# FORCE bomb placement for deterministic testing
	ai.request_bomb_placement()
	await ctx.tick.step_frames(2)  # Let GameInstance process
	
	var bomb_placed = game.bombs.size() > 0
	var block_destroyed = false
	var survived = true
	var max_frames = 400
	for i in range(max_frames):
		await ctx.tick.step_frames(1)
		# Check block removal
		if bomb_placed and game.game_map[soft_tile.y][soft_tile.x] == 0:
			block_destroyed = true
			break
		if ai.is_dead:
			survived = false
			break
	# Assertions
	ctx.assert.assert_true(bomb_placed, "Bomb was not placed")
	ctx.assert.assert_true(block_destroyed, "Soft block not destroyed")
	ctx.assert.assert_true(survived, "AI died during test")
	var summary = ctx.assert.summary()
	var ok = summary.failed == 0
	var msg = "Bomb destroyed soft block"
	if not ok:
		msg = str(summary.failures)
	return {"ok": ok, "message": msg}
