extends Node

# AI moves from spawn A to target B (second spawn point) using map_factory.small_open()

func run(ctx) -> Dictionary:
	ctx.assert.clear()
	var map_dict = ctx.map_factory.small_open()
	var game = await ctx.ai_spawn.make_game(map_dict)
	game.load_custom_map(map_dict)
	# Spawn AI at first spawn (Balanced personality=0)
	var ai = ctx.ai_spawn.spawn_ai(game, 0, 0)
	# Define target tile from second spawn point and spawn a power-up to create a goal
	var target_pos: Vector2 = map_dict.spawn_points[1]
	var target_tile := Vector2i(int(floor(target_pos.x/64)), int(floor(target_pos.y/64)))
	game.spawn_powerup(target_tile)
	var max_frames = 600  # ~10s at 60fps (increased from 300)
	var reached = false
	var last_tile = ai.get_tile_position()
	var stuck_counter = 0
	for i in range(max_frames):
		await ctx.tick.step_frames(1)
		var ai_tile = ai.get_tile_position()
		# Check for stuck condition
		if ai_tile == last_tile:
			stuck_counter += 1
		else:
			stuck_counter = 0
			last_tile = ai_tile
		if ai_tile == target_tile:
			reached = true
			break
	# Assertions
	ctx.assert.assert_true(reached, "AI did not reach target tile within frame budget")
	var summary = ctx.assert.summary()
	var ok = summary.failed == 0
	var msg = "Reached target"
	if not ok:
		msg = str(summary.failures)
	return {"ok": ok, "message": msg}
