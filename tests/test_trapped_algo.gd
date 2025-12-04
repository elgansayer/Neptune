extends SceneTree

# Test script for Trapped Animation Algorithm
# Verifies the logic of _is_player_physically_trapped in isolation.

var game_map = []
var bombs = {}

func _init():
	print("Starting Trapped Animation Algorithm Test...")
	_run_test()
	quit()

func _run_test():
	# Setup map 3x3
	# 1 1 1
	# 1 0 1
	# 1 1 1
	game_map = [
		[1, 1, 1],
		[1, 0, 1],
		[1, 1, 1]
	]
	
	print("Test 1: Player at (1,1), right side open")
	game_map[1][2] = 0 # Right side open
	
	var is_trapped = _is_player_physically_trapped(Vector2i(1, 1))
	print("Is trapped (should be false): ", is_trapped)
	if is_trapped:
		print("FAIL: Player should not be trapped")
	else:
		print("PASS: Player is not trapped")
		
	print("Test 2: Block right side with bomb")
	# Mock bomb
	var bomb = Node.new()
	bomb.set_meta("tile", Vector2i(2, 1))
	bombs["bomb1"] = bomb
	
	is_trapped = _is_player_physically_trapped(Vector2i(1, 1))
	print("Is trapped (should be true): ", is_trapped)
	if is_trapped:
		print("PASS: Player is trapped by walls and bomb")
	else:
		print("FAIL: Player should be trapped")
		
	print("Test 3: Remove bomb, place soft block")
	bombs.clear()
	game_map[1][2] = 2 # Soft block
	
	is_trapped = _is_player_physically_trapped(Vector2i(1, 1))
	print("Is trapped (should be true): ", is_trapped)
	if is_trapped:
		print("PASS: Player is trapped by walls and soft block")
	else:
		print("FAIL: Player should be trapped")

# Copied from game_instance.gd
func _is_player_physically_trapped(center_tile: Vector2i) -> bool:
	"""
	Check if a player is physically trapped on all 4 sides.
	Returns true if UP, DOWN, LEFT, and RIGHT are all impassable
	(walls, blocks, hurry blocks, or bombs).
	"""
	var directions = [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]
	
	for dir in directions:
		var check_pos = center_tile + dir
		
		# Check map bounds
		if check_pos.y < 0 or check_pos.y >= game_map.size() or \
		   check_pos.x < 0 or check_pos.x >= game_map[0].size():
			continue # Out of bounds counts as blocked
			
		# Check for walls (1), soft blocks (2), or hurry blocks (3)
		var tile_type = game_map[check_pos.y][check_pos.x]
		if tile_type == 1 or tile_type == 2 or tile_type == 3:
			continue # Blocked by static map element
			
		# Check for bombs
		var has_bomb = false
		for bomb_id in bombs:
			var bomb = bombs[bomb_id]
			# Modified for test: check valid instance and get_tile_position
			# In test we use Node and meta
			if is_instance_valid(bomb):
				var bomb_pos = Vector2i.ZERO
				if bomb.has_method("get_tile_position"):
					bomb_pos = bomb.get_tile_position()
				else:
					bomb_pos = bomb.get_meta("tile")
					
				if bomb_pos == check_pos:
					has_bomb = true
					break
		
		if has_bomb:
			continue # Blocked by bomb
			
		# If we get here, this direction is open!
		return false
		
	# If we checked all directions and didn't find an opening, we are trapped
	return true
