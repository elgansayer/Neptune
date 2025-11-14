extends Node2D

# Power Glove Bomb Throwing System Test
# Tests the server-authoritative throw mechanics and client prediction

const ServerBomb = preload("res://shared/entities/server_bomb.gd")
const ServerPlayer = preload("res://shared/entities/server_player.gd")

var test_player: ServerPlayer
var test_bomb: ServerBomb
var test_results := []

func _ready():
	print("\n========== POWER GLOVE SYSTEM TEST ==========")
	run_all_tests()
	print_test_results()
	print("============================================\n")

func run_all_tests():
	"""Run all Power Glove system tests"""
	test_bomb_state_enum()
	test_bomb_pickup_eligibility()
	test_bomb_pickup()
	test_bomb_throw_calculation()
	test_bomb_bounce_logic()
	test_mid_air_explosion()
	test_player_carry_state()

func test_bomb_state_enum():
	"""Test: Bomb state enum values are defined correctly"""
	var bomb = ServerBomb.new()
	
	var test_name = "Bomb State Enum"
	var passed = true
	var message = ""
	
	# Check initial state
	if bomb.bomb_state != ServerBomb.BombState.PLANTED:
		passed = false
		message = "Initial state should be PLANTED"
	
	# Check state enum exists
	if not ServerBomb.BombState.has("CARRIED"):
		passed = false
		message = "BombState.CARRIED not defined"
	
	if not ServerBomb.BombState.has("THROWN"):
		passed = false
		message = "BombState.THROWN not defined"
	
	if not ServerBomb.BombState.has("LANDED"):
		passed = false
		message = "BombState.LANDED not defined"
	
	test_results.append({
		"name": test_name,
		"passed": passed,
		"message": message if not passed else "All states defined correctly"
	})
	
	bomb.queue_free()

func test_bomb_pickup_eligibility():
	"""Test: Bomb can only be picked up when eligible"""
	var bomb = ServerBomb.new()
	add_child(bomb)
	
	var test_name = "Bomb Pickup Eligibility"
	var passed = true
	var message = ""
	
	# Test 1: PLANTED bomb can be picked up
	bomb.bomb_state = ServerBomb.BombState.PLANTED
	bomb.has_exploded = false
	if not bomb.can_be_picked_up():
		passed = false
		message = "PLANTED bomb should be pickable"
	
	# Test 2: CARRIED bomb cannot be picked up
	bomb.bomb_state = ServerBomb.BombState.CARRIED
	if bomb.can_be_picked_up():
		passed = false
		message = "CARRIED bomb should not be pickable"
	
	# Test 3: Exploding bomb cannot be picked up
	bomb.bomb_state = ServerBomb.BombState.PLANTED
	bomb.has_exploded = true
	if bomb.can_be_picked_up():
		passed = false
		message = "Exploding bomb should not be pickable"
	
	test_results.append({
		"name": test_name,
		"passed": passed,
		"message": message if not passed else "Pickup eligibility works correctly"
	})
	
	bomb.queue_free()

func test_bomb_pickup():
	"""Test: Player can pick up bomb with Power Glove"""
	var player = ServerPlayer.new()
	var bomb = ServerBomb.new()
	add_child(player)
	add_child(bomb)
	
	player.position = Vector2(64, 64)
	bomb.position = Vector2(64, 64)
	player.has_power_glove = true
	bomb.bomb_id = "test_bomb_1"
	
	var test_name = "Bomb Pickup"
	var passed = true
	var message = ""
	
	# Test pickup
	var pickup_success = bomb.pick_up(player)
	
	if not pickup_success:
		passed = false
		message = "Pickup failed"
	elif bomb.bomb_state != ServerBomb.BombState.CARRIED:
		passed = false
		message = "State not changed to CARRIED"
	elif bomb.carrying_player != player:
		passed = false
		message = "Carrying player not set"
	elif bomb.carrier_id != player.player_id:
		passed = false
		message = "Carrier ID not set"
	
	test_results.append({
		"name": test_name,
		"passed": passed,
		"message": message if not passed else "Pickup successful"
	})
	
	player.queue_free()
	bomb.queue_free()

func test_bomb_throw_calculation():
	"""Test: Bomb throw target calculation"""
	var player = ServerPlayer.new()
	var bomb = ServerBomb.new()
	add_child(player)
	add_child(bomb)
	
	# Setup mock game map (simple empty 10x10 grid)
	var mock_map = []
	for y in range(10):
		var row = []
		for x in range(10):
			row.append(0)  # All empty
		mock_map.append(row)
	
	# Position at center
	player.position = Vector2(320, 320)  # Tile (5, 5) at 64px tiles
	bomb.position = player.position
	bomb.bomb_id = "test_bomb_2"
	bomb.bomb_state = ServerBomb.BombState.CARRIED
	bomb.carrying_player = player
	
	var test_name = "Bomb Throw Calculation"
	var passed = true
	var message = ""
	
	# Mock the game_instance
	var mock_instance = Node.new()
	mock_instance.set_script(GDScript.new())
	mock_instance.game_map = mock_map
	bomb.game_instance = mock_instance
	
	# Test throw
	var throw_success = bomb.throw_bomb(Vector2.RIGHT)
	
	if not throw_success:
		passed = false
		message = "Throw failed"
	elif bomb.bomb_state != ServerBomb.BombState.THROWN:
		passed = false
		message = "State not changed to THROWN"
	elif bomb.throw_direction != Vector2.RIGHT:
		passed = false
		message = "Direction not set correctly"
	
	test_results.append({
		"name": test_name,
		"passed": passed,
		"message": message if not passed else "Throw calculation successful"
	})
	
	player.queue_free()
	bomb.queue_free()
	mock_instance.queue_free()

func test_bomb_bounce_logic():
	"""Test: Bomb bounces when landing on obstacle"""
	var test_name = "Bomb Bounce Logic"
	var passed = true
	var message = "Bounce logic requires integration test"
	
	# This test would require a full game instance with map
	# For now, just verify the method exists
	var bomb = ServerBomb.new()
	if not bomb.has_method("_find_bounce_tile"):
		passed = false
		message = "_find_bounce_tile method not found"
	
	test_results.append({
		"name": test_name,
		"passed": passed,
		"message": message
	})
	
	bomb.queue_free()

func test_mid_air_explosion():
	"""Test: Bomb can explode mid-air"""
	var bomb = ServerBomb.new()
	add_child(bomb)
	
	bomb.bomb_id = "test_bomb_3"
	bomb.bomb_state = ServerBomb.BombState.THROWN
	bomb.position = Vector2(100, 100)
	bomb.current_z_height = 50.0  # Mid-air
	
	var test_name = "Mid-Air Explosion"
	var passed = true
	var message = ""
	
	# Trigger explosion while thrown
	bomb.explode()
	
	if not bomb.has_exploded:
		passed = false
		message = "Bomb did not explode"
	elif not bomb.explosion_started:
		passed = false
		message = "Explosion did not start"
	
	test_results.append({
		"name": test_name,
		"passed": passed,
		"message": message if not passed else "Mid-air explosion works"
	})
	
	bomb.queue_free()

func test_player_carry_state():
	"""Test: Player tracking of carried bomb"""
	var player = ServerPlayer.new()
	var bomb = ServerBomb.new()
	add_child(player)
	add_child(bomb)
	
	player.player_id = "test_player"
	player.has_power_glove = true
	player.position = Vector2(128, 128)
	bomb.position = Vector2(128, 128)
	bomb.bomb_id = "test_bomb_4"
	
	var test_name = "Player Carry State"
	var passed = true
	var message = ""
	
	# Pickup bomb
	if not player.try_pickup_bomb(bomb):
		passed = false
		message = "Failed to pickup bomb"
	elif not player.is_carrying_bomb():
		passed = false
		message = "is_carrying_bomb() returned false"
	elif player.carried_bomb != bomb:
		passed = false
		message = "carried_bomb reference not set"
	
	# Test throw
	if passed and not player.throw_carried_bomb():
		passed = false
		message = "Failed to throw bomb"
	elif passed and player.is_carrying_bomb():
		passed = false
		message = "Still carrying after throw"
	
	test_results.append({
		"name": test_name,
		"passed": passed,
		"message": message if not passed else "Player carry state works correctly"
	})
	
	player.queue_free()
	bomb.queue_free()

func print_test_results():
	"""Print summary of all test results"""
	var passed_count = 0
	var failed_count = 0
	
	for result in test_results:
		var status = "✅ PASS" if result.passed else "❌ FAIL"
		print("%s: %s - %s" % [status, result.name, result.message])
		
		if result.passed:
			passed_count += 1
		else:
			failed_count += 1
	
	print("\nTest Summary: %d passed, %d failed out of %d total" % 
		  [passed_count, failed_count, test_results.size()])
