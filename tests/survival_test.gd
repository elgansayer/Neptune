extends "res://tests/bot_test_suite.gd"

func test_escape_own_bomb_open_area() -> Variant:
	# Setup: Bot in 7x7 clear area
	# Clear 7x7 area around center
	var center = Vector2i(7, 6)
	for y in range(center.y - 3, center.y + 4):
		for x in range(center.x - 3, center.x + 4):
			set_tile(x, y, 0) # Empty
			
	# Spawn bot at center
	spawn_bot_at(center)
	
	if not is_instance_valid(bot_player):
		return "Failed to spawn bot"
		
	# Force bot to place bomb
	# We can simulate input or call place_bomb directly
	game_instance.place_bomb(bot_player)
	
	# Verify bomb placed
	if game_instance.bombs.is_empty():
		return "Bot failed to place bomb"
		
	# Wait for bot to move away
	# Expect move > 2 tiles away within 2s
	var initial_pos = bot_player.get_tile_position()
	
	await wait_for_condition(func():
		var current_pos = bot_player.get_tile_position()
		var dist = abs(current_pos.x - initial_pos.x) + abs(current_pos.y - initial_pos.y)
		return dist > 2
	, 2.0)
	
	var final_pos = bot_player.get_tile_position()
	var dist = abs(final_pos.x - initial_pos.x) + abs(final_pos.y - initial_pos.y)
	
	if dist <= 2:
		return "Bot did not escape far enough (dist: %d)" % dist
		
	# Wait for explosion (bomb timer is usually 3s)
	# We can speed up time or just wait
	await get_tree().create_timer(3.5).timeout
	
	if bot_player.is_dead:
		return "Bot died from explosion"
		
	return true

func test_escape_own_bomb_corner() -> Variant:
	# Setup: Bot in corner (1, 1) surrounded by walls
	# Walls at (0,1) and (1,0) are hard walls (edge of map usually)
	# Let's make a custom corner at (3,3)
	var corner = Vector2i(3, 3)
	
	# Clear area
	for y in range(corner.y, corner.y + 5):
		for x in range(corner.x, corner.x + 5):
			set_tile(x, y, 0)
			
	# Build walls
	set_tile(corner.x - 1, corner.y, 1) # Left wall
	set_tile(corner.x, corner.y - 1, 1) # Top wall
	
	spawn_bot_at(corner)
	
	game_instance.place_bomb(bot_player)
	
	# Expect diagonal escape (3,3) -> (4,4) or similar
	var initial_pos = bot_player.get_tile_position()
	
	await wait_for_condition(func():
		var current_pos = bot_player.get_tile_position()
		return current_pos != initial_pos
	, 2.0)
	
	var moved_pos = bot_player.get_tile_position()
	if moved_pos == initial_pos:
		return "Bot did not move from corner"
		
	# Wait for explosion
	await get_tree().create_timer(3.5).timeout
	
	if bot_player.is_dead:
		return "Bot died in corner"
		
	return true
