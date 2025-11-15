extends SceneTree

## Test script for UtilityScorer functionality

const UtilityScorer = preload("res://shared/ai/decision/utility_scorer.gd")

func _init():
	print("=== UtilityScorer Test ===")
	
	# Create scorer instance
	var scorer = UtilityScorer.new()
	print("✓ UtilityScorer instantiated")
	
	# Test reward constants
	assert(scorer.REWARD_GET_FIRE_UP == 100.0, "REWARD_GET_FIRE_UP should be 100.0")
	assert(scorer.REWARD_KILL_OPPONENT == 400.0, "REWARD_KILL_OPPONENT should be 400.0")
	assert(scorer.REWARD_BAIT_PANIC == 500.0, "REWARD_BAIT_PANIC should be 500.0")
	assert(scorer.RISK_DEATH == -500.0, "RISK_DEATH should be -500.0")
	print("✓ Reward constants validated")
	
	# Test get_bomb_safety_score (without checker configured)
	var safety_score = scorer.get_bomb_safety_score(
		Vector2i(5, 5),  # bot_pos
		1,  # bomb_range
		5.0,  # bot_speed
		0.0  # current_time_msec
	)
	assert(safety_score == 0.5, "Safety score should default to 0.5 when checker not configured")
	print("✓ get_bomb_safety_score returns default 0.5")
	
	# Test score_establish_territory (safe farming)
	var territory_utility = scorer.score_establish_territory(
		Vector2i(5, 5),  # bot_pos
		1,  # bomb_range
		0.9,  # can_place_bomb_score (safe)
		0.0  # current_time_msec
	)
	# Expected: (5.0 * 0.99) - (-500.0 * 0.1) = 4.95 + 50.0 = 54.95
	var expected_territory = (5.0 * 0.99) - (-500.0 * 0.1)
	assert(abs(territory_utility - expected_territory) < 0.01, "Territory utility calculation incorrect")
	print("✓ score_establish_territory: %.2f (expected: %.2f)" % [territory_utility, expected_territory])
	
	# Test score_nuisance_bomb (different quadrants)
	var nuisance_utility = scorer.score_nuisance_bomb(
		Vector2i(5, 5),  # bot_pos
		1,  # enemy_quadrant
		0,  # bot_quadrant (different)
		0.9  # can_place_bomb_score
	)
	# Expected: (10.0 * 0.99) - (-500.0 * 0.1) = 9.9 + 50.0 = 59.9
	var expected_nuisance = (10.0 * 0.99) - (-500.0 * 0.1)
	assert(abs(nuisance_utility - expected_nuisance) < 0.01, "Nuisance utility calculation incorrect")
	print("✓ score_nuisance_bomb: %.2f (expected: %.2f)" % [nuisance_utility, expected_nuisance])
	
	# Test score_nuisance_bomb (same quadrant = 0.0)
	var nuisance_same_quadrant = scorer.score_nuisance_bomb(
		Vector2i(5, 5),
		0,  # enemy_quadrant
		0,  # bot_quadrant (SAME)
		0.9
	)
	assert(nuisance_same_quadrant == 0.0, "Nuisance utility should be 0.0 when in same quadrant")
	print("✓ score_nuisance_bomb (same quadrant): 0.0")
	
	# Test score_kick_snipe
	var kick_utility = scorer.score_kick_snipe(
		Vector2i(5, 5),  # bot_pos
		Vector2i(10, 5),  # enemy_pos
		5.0,  # enemy_dist (5 tiles)
		0.3,  # panic_bomber_rating (not panicky)
		0.8  # can_place_bomb_score
	)
	# P_Success = (1.0/5.0) * (1.0 - 0.3) = 0.2 * 0.7 = 0.14
	# P_Failure = 1.0 - 0.8 = 0.2
	# Utility = (400.0 * 0.14) - (-500.0 * 0.2) = 56.0 + 100.0 = 156.0
	var expected_kick = (400.0 * 0.14) - (-500.0 * 0.2)
	assert(abs(kick_utility - expected_kick) < 0.01, "Kick snipe utility calculation incorrect")
	print("✓ score_kick_snipe: %.2f (expected: %.2f)" % [kick_utility, expected_kick])
	
	# Test score_bait_panic_bomb
	var bait_utility = scorer.score_bait_panic_bomb(
		Vector2i(5, 5),  # bot_pos
		Vector2i(8, 5),  # enemy_pos
		0.9,  # panic_bomber_rating (HIGH - easy to bait)
		0.85  # can_place_bomb_score
	)
	# P_Success = 0.9 * 0.8 = 0.72
	# P_Failure = 1.0 - 0.85 = 0.15
	# Utility = (500.0 * 0.72) - (-500.0 * 0.15) = 360.0 + 75.0 = 435.0
	var expected_bait = (500.0 * 0.72) - (-500.0 * 0.15)
	assert(abs(bait_utility - expected_bait) < 0.01, "Bait panic utility calculation incorrect")
	print("✓ score_bait_panic_bomb: %.2f (expected: %.2f)" % [bait_utility, expected_bait])
	
	print("\n=== All UtilityScorer tests PASSED ✅ ===\n")
	
	quit()
