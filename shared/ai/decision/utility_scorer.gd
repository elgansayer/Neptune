extends Resource
class_name UtilityScorer

## Mathematical utility-based decision making for bot actions
## Based on Bomberman AI Doctrine - Module 8: Utility Function
## Formula: Utility = (Reward * P_Success) - (Risk * P_Failure)

const Constants = preload("res://shared/constants.gd")

# Action reward values (base scores)
const REWARD_GET_FIRE_UP := 100.0
const REWARD_GET_BOMB_UP := 80.0
const REWARD_GET_SPEED_UP := 70.0
const REWARD_KILL_OPPONENT := 400.0
const REWARD_BAIT_PANIC := 500.0
const REWARD_NUISANCE_BOMB := 10.0
const REWARD_ESTABLISH_TERRITORY := 5.0

# Risk values
const RISK_DEATH := -500.0

var _ai_manager = null
var _grid_sampler = null
var _bomb_safety_checker = null

func configure(ai_manager, grid_sampler, safety_checker) -> void:
	_ai_manager = ai_manager
	_grid_sampler = grid_sampler
	_bomb_safety_checker = safety_checker

## Score: Get Fire-Up powerup
func score_get_powerup(
	bot_pos: Vector2i, 
	powerup_pos: Vector2i, 
	powerup_type: String,
	enemy_dist_to_powerup: float,
	can_place_bomb_score: float,
	current_time_msec: float
) -> float:
	
	var reward := REWARD_ESTABLISH_TERRITORY
	if powerup_type == "fire_up":
		reward = REWARD_GET_FIRE_UP
	elif powerup_type == "bomb_up":
		reward = REWARD_GET_BOMB_UP
	elif powerup_type == "speed_up":
		reward = REWARD_GET_SPEED_UP
	
	# Calculate path distance (time to reach)
	if _ai_manager == null or _ai_manager.pathfinder == null:
		return 0.0
	
	var pathfinder = _ai_manager.pathfinder
	pathfinder.threat_matrix_ref = _ai_manager.get_current_threat_matrix()
	pathfinder.path_start_time_msec = current_time_msec
	pathfinder.path_start_pos = bot_pos
	pathfinder.bot_speed_msec_per_tile = 200.0
	
	var path = pathfinder.get_timed_point_path(bot_pos, powerup_pos)
	if path.is_empty():
		return 0.0  # No path = impossible
	
	var my_path_time: float = path.size() * 200.0  # msec
	var enemy_path_time: float = enemy_dist_to_powerup * 200.0  # msec
	
	# P_Success = likelihood we reach it first
	var p_success: float = 0.0
	if enemy_path_time > 0:
		p_success = 1.0 - (my_path_time / enemy_path_time)
		p_success = clamp(p_success, 0.0, 1.0)
	else:
		p_success = 1.0  # No competition
	
	# P_Failure = likelihood we die trying
	var p_failure := 1.0 - can_place_bomb_score
	
	# Utility = (Reward * P_Success) - (Risk * P_Failure)
	return (reward * p_success) - (RISK_DEATH * p_failure)

## Score: Execute KickSnipe (offensive bomb placement)
func score_kick_snipe(
	bot_pos: Vector2i,
	enemy_pos: Vector2i,
	enemy_dist: float,
	panic_bomber_rating: float,
	can_place_bomb_score: float
) -> float:
	
	var reward := REWARD_KILL_OPPONENT
	
	# P_Success based on distance and enemy panic rating
	var distance_factor: float = 1.0 / max(1.0, enemy_dist)
	var panic_factor := 1.0 - panic_bomber_rating
	var p_success: float = distance_factor * panic_factor
	p_success = clamp(p_success, 0.0, 1.0)
	
	# P_Failure = likelihood we die from our own bomb
	var p_failure := 1.0 - can_place_bomb_score
	
	return (reward * p_success) - (RISK_DEATH * p_failure)

## Score: Bait Panic Bomb (feint attack to trigger enemy bomb)
func score_bait_panic_bomb(
	bot_pos: Vector2i,
	enemy_pos: Vector2i,
	panic_bomber_rating: float,
	can_place_bomb_score: float
) -> float:
	
	var reward := REWARD_BAIT_PANIC
	
	# P_Success = how likely enemy will panic
	var p_success := panic_bomber_rating * 0.8  # 80% reliability
	p_success = clamp(p_success, 0.0, 1.0)
	
	# P_Failure = we fail to bait or die
	var p_failure := 1.0 - can_place_bomb_score
	
	return (reward * p_success) - (RISK_DEATH * p_failure)

## Score: Nuisance Bombing (harassment)
func score_nuisance_bomb(
	bot_pos: Vector2i,
	enemy_quadrant: int,
	bot_quadrant: int,
	can_place_bomb_score: float
) -> float:
	
	var reward := REWARD_NUISANCE_BOMB
	
	# P_Success = almost always works
	var p_success := 0.99
	
	# P_Failure = we die
	var p_failure := 1.0 - can_place_bomb_score
	
	# Only do this if we're NOT in same quadrant as enemy
	if bot_quadrant == enemy_quadrant:
		return 0.0
	
	return (reward * p_success) - (RISK_DEATH * p_failure)

## Score: Establish Territory (farming/safe bomb placement)
func score_establish_territory(
	bot_pos: Vector2i,
	bomb_range: int,
	can_place_bomb_score: float,
	current_time_msec: float
) -> float:
	
	var reward := REWARD_ESTABLISH_TERRITORY
	
	# P_Success = very high for safe farming
	var p_success := 0.99
	
	# P_Failure = we die
	var p_failure := 1.0 - can_place_bomb_score
	
	return (reward * p_success) - (RISK_DEATH * p_failure)

## Get can_place_bomb safety score (0.0 = suicide, 1.0 = safe)
func get_bomb_safety_score(
	bot_pos: Vector2i,
	bomb_range: int,
	bot_speed: float,
	current_time_msec: float
) -> float:
	
	if _bomb_safety_checker == null:
		return 0.5  # Unknown
	
	var is_safe: bool = _bomb_safety_checker.can_safely_plant_bomb(
		bot_pos, bot_pos, bomb_range, bot_speed, current_time_msec
	)
	
	return 1.0 if is_safe else 0.0

## Calculate utility for all available actions and return best
func select_best_action(
	bot_pos: Vector2i,
	bot_bomb_range: int,
	bot_speed: float,
	nearest_enemy_pos: Vector2i,
	nearest_enemy_id: int,
	nearest_powerup_pos: Vector2i,
	powerup_type: String,
	current_time_msec: float
) -> Dictionary:
	
	var utilities := {}
	
	# Get safety score (used by all actions)
	var safety_score := get_bomb_safety_score(bot_pos, bot_bomb_range, bot_speed, current_time_msec)
	
	# Get enemy intelligence
	var panic_rating := 0.0
	var enemy_quadrant := -1
	if _ai_manager != null and nearest_enemy_id >= 0:
		var profile = _ai_manager.get_opponent_profile(nearest_enemy_id, "")
		panic_rating = profile.panic_bomber_rating
		enemy_quadrant = profile.favourite_quadrant
	
	# Score: Get Powerup
	if nearest_powerup_pos != Vector2i(-1, -1):
		var enemy_dist := float(_grid_sampler.get_manhattan_distance(nearest_enemy_pos, nearest_powerup_pos)) if nearest_enemy_pos != Vector2i(-1, -1) else 999.0
		utilities["get_powerup"] = score_get_powerup(
			bot_pos, nearest_powerup_pos, powerup_type, enemy_dist, safety_score, current_time_msec
		)
	
	# Score: KickSnipe
	if nearest_enemy_pos != Vector2i(-1, -1):
		var enemy_dist := float(_grid_sampler.get_manhattan_distance(bot_pos, nearest_enemy_pos))
		utilities["kick_snipe"] = score_kick_snipe(
			bot_pos, nearest_enemy_pos, enemy_dist, panic_rating, safety_score
		)
	
	# Score: Bait Panic Bomb
	if nearest_enemy_pos != Vector2i(-1, -1) and panic_rating > 0.7:
		utilities["bait_panic"] = score_bait_panic_bomb(
			bot_pos, nearest_enemy_pos, panic_rating, safety_score
		)
	
	# Score: Nuisance Bomb
	if nearest_enemy_pos != Vector2i(-1, -1):
		var bot_quadrant := _get_quadrant(bot_pos)
		utilities["nuisance_bomb"] = score_nuisance_bomb(
			bot_pos, enemy_quadrant, bot_quadrant, safety_score
		)
	
	# Score: Establish Territory (always available)
	utilities["establish_territory"] = score_establish_territory(
		bot_pos, bot_bomb_range, safety_score, current_time_msec
	)
	
	# Find best action
	var best_action := "establish_territory"
	var best_utility := -INF
	
	for action in utilities:
		if utilities[action] > best_utility:
			best_utility = utilities[action]
			best_action = action
	
	return {
		"action": best_action,
		"utility": best_utility,
		"all_utilities": utilities
	}

func _get_quadrant(pos: Vector2i) -> int:
	if _ai_manager == null:
		return -1
	return _ai_manager._get_quadrant(pos)
