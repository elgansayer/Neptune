extends Node
class_name ServerBotController

const BTNode = preload("res://shared/ai/behavior_tree/nodes/base_node.gd")
const BehaviorTreeRunner = preload("res://shared/ai/behavior_tree/bt_runner.gd")
const BTSequence = preload("res://shared/ai/behavior_tree/nodes/sequence.gd")
const BTUtilitySelector = preload("res://shared/ai/behavior_tree/nodes/utility_selector.gd")
const BTEscapeNode = preload("res://shared/ai/behavior_tree/nodes/leaf_find_escape.gd")
const BTMoveToNode = preload("res://shared/ai/behavior_tree/nodes/leaf_move_to.gd")
const BTCollectPowerUpNode = preload("res://shared/ai/behavior_tree/nodes/leaf_collect_powerup.gd")
const BTPlaceBombNode = preload("res://shared/ai/behavior_tree/nodes/leaf_place_bomb.gd")
const BTWaitAmbushNode = preload("res://shared/ai/behavior_tree/nodes/leaf_wait_ambush.gd")
const BTChaseOpponentNode = preload("res://shared/ai/behavior_tree/nodes/leaf_chase_opponent.gd")
const AIPersonalitiesConfig = preload("res://shared/ai/config/personalities.gd")
const OpeningGambit = preload("res://shared/ai/planning/opening_gambit.gd")
const UtilityScorer = preload("res://shared/ai/decision/utility_scorer.gd")

## Behavior-tree-powered controller that simulates authoritative inputs for AI players.

var game_instance
var personality := "BALANCED"
var player_ref
var grid_sampler
var hazard_predictor
var opponent_tracker
var bomb_planner

var _bt_runner
var _blackboard := {}
var _behavior_weights := {}
var _personality_profile := {}
var _decision_interval := 0.1
var _decision_accumulator := 0.0

var _escape_sequence
var _attack_sequence
var _collect_sequence
var _ambush_node
var bomb_safety_checker  # New: time-aware BFS suicide check
var opening_gambit: OpeningGambit  # Opening strategy planner
var utility_scorer: UtilityScorer  # Mathematical (Reward * P_Success) - (Risk * P_Failure)

# State machine for opening gambit
enum BotState { ANALYZING_SPAWN, MOVING_TO_FIRST_BOMB, PLANTING_FIRST_BOMB, WAITING_FOR_BLAST, FARMING, NORMAL }
var _current_state: BotState = BotState.ANALYZING_SPAWN
var _first_target: Vector2i = Vector2i.ZERO
var _second_target: Vector2i = Vector2i.ZERO
var _has_planted_first_bomb := false

func configure(instance, player, personality_name: String,
		sampler, predictor,
		tracker, planner, safety_checker) -> void:
	game_instance = instance
	player_ref = player
	grid_sampler = sampler
	hazard_predictor = predictor
	opponent_tracker = tracker
	bomb_planner = planner
	bomb_safety_checker = safety_checker
	
	# Initialize opening gambit planner
	opening_gambit = OpeningGambit.new()
	# Initialize utility scorer
	utility_scorer = UtilityScorer.new()
	# Will configure after game_instance.ai_manager is ready
	call_deferred("_configure_opening_gambit")
	call_deferred("_configure_utility_scorer")
	
	personality = personality_name
	_personality_profile = AIPersonalitiesConfig.get_profile(personality_name)
	_decision_interval = _personality_profile.get("decision_interval", 0.1)
	_build_behavior_tree()
	if player_ref:
		player_ref.tree_exited.connect(_on_player_removed, Object.CONNECT_ONE_SHOT)

func _configure_opening_gambit() -> void:
	if game_instance != null and game_instance.ai_manager != null:
		opening_gambit.configure(game_instance.ai_manager, grid_sampler, bomb_safety_checker)
		print("[BotController] OpeningGambit configured for ", player_ref.player_name if player_ref else "bot")

func _configure_utility_scorer() -> void:
	if game_instance != null and game_instance.ai_manager != null:
		utility_scorer.configure(game_instance.ai_manager, grid_sampler, bomb_safety_checker)
		print("[BotController] UtilityScorer configured for ", player_ref.player_name if player_ref else "bot")

func _build_behavior_tree() -> void:
	_escape_sequence = BTSequence.new()
	_escape_sequence.children = [BTEscapeNode.new(), BTMoveToNode.new()]
	_attack_sequence = BTSequence.new()
	# Attack: chase opponent, place bomb, then IMMEDIATELY move to safety
	_attack_sequence.children = [BTChaseOpponentNode.new(), BTPlaceBombNode.new(), BTMoveToNode.new()]
	_collect_sequence = BTSequence.new()
	_collect_sequence.children = [BTCollectPowerUpNode.new(), BTMoveToNode.new()]
	_ambush_node = BTWaitAmbushNode.new()
	var utility_selector = BTUtilitySelector.new()
	utility_selector.children = [_escape_sequence, _attack_sequence, _collect_sequence, _ambush_node]
	utility_selector.score_func = Callable(self, "_score_behavior")
	_bt_runner = BehaviorTreeRunner.new()
	_bt_runner.set_root(utility_selector)
	_behavior_weights = {
		_escape_sequence: _personality_profile.get("escape_bias", 1.0),
		_attack_sequence: _personality_profile.get("attack_bias", 1.0),
		_collect_sequence: _personality_profile.get("powerup_bias", 0.8),
		_ambush_node: _personality_profile.get("ambush_bias", 0.2)
	}

func _physics_process(delta: float) -> void:
	if not is_instance_valid(player_ref) or player_ref.is_dead:
		return
	if _bt_runner == null:
		return
	
	# Opening Gambit State Machine (overrides normal behavior tree during opening)
	if _current_state != BotState.NORMAL:
		_execute_opening_gambit(delta)
		return
	
	# Normal behavior tree execution
	_decision_accumulator += delta
	if _decision_accumulator < _decision_interval:
		return
	_decision_accumulator = 0.0
	_update_blackboard()
	_bt_runner.set_blackboard(_blackboard)
	_bt_runner.tick(_decision_interval)
	_apply_outputs()

func _update_blackboard() -> void:
	_blackboard.clear()
	_blackboard["game_instance"] = game_instance
	_blackboard["grid_sampler"] = grid_sampler
	_blackboard["hazard_predictor"] = hazard_predictor
	_blackboard["opponent_tracker"] = opponent_tracker
	_blackboard["bomb_planner"] = bomb_planner
	_blackboard["bomb_safety_checker"] = bomb_safety_checker
	_blackboard["ai_manager"] = game_instance.ai_manager if game_instance else null
	_blackboard["player"] = player_ref
	_blackboard["personality"] = _personality_profile
	_blackboard["time"] = Time.get_ticks_msec() / 1000.0
	_blackboard["danger_buffer"] = _personality_profile.get("danger_buffer", 0.1)
	_blackboard["escape_radius"] = _personality_profile.get("escape_radius", 8)
	_blackboard["path_depth"] = _personality_profile.get("path_depth", 40)
	_blackboard["current_tile"] = player_ref.get_tile_position()
	_blackboard["current_world"] = player_ref.position
	var nearest = opponent_tracker.get_nearest_opponent(player_ref.position)
	_blackboard["nearest_opponent"] = nearest
	if nearest:
		_blackboard["opponent_tile"] = nearest.get("tile")
	else:
		_blackboard["opponent_tile"] = null
	_blackboard["move_vector"] = Vector2.ZERO
	_blackboard["request_bomb"] = false

func _apply_outputs() -> void:
	if not is_instance_valid(player_ref):
		return
	var desired: Vector2 = _blackboard.get("move_vector", Vector2.ZERO)
	var axis := Vector2.ZERO
	if desired.length() > 0.05:
		if abs(desired.x) > abs(desired.y):
			axis = Vector2(sign(desired.x), 0.0)
		else:
			axis = Vector2(0.0, sign(desired.y))
	player_ref.set_input(axis.x, axis.y)
	if _blackboard.get("request_bomb", false):
		game_instance.place_bomb(player_ref)
	_blackboard["request_bomb"] = false

func _score_behavior(child, blackboard: Dictionary) -> float:
	var base := float(_behavior_weights.get(child, 0.1))
	var current_tile: Vector2i = blackboard.get("current_tile")
	var now = blackboard.get("time", 0.0)
	var current_time_msec := Time.get_ticks_msec()
	
	# UTILITY FUNCTION OVERRIDE: Use mathematical decision-making if scorer is configured
	if utility_scorer != null and _personality_profile.get("use_utility_function", true):
		var nearest_enemy_pos := Vector2i(-1, -1)
		var nearest_enemy_id := -999
		var nearest_opponent = blackboard.get("nearest_opponent")
		if nearest_opponent:
			var tile = nearest_opponent.get("tile", null)
			if tile != null:
				nearest_enemy_pos = tile
			nearest_enemy_id = nearest_opponent.get("peer_id", -999)
		
		var nearest_powerup_pos := Vector2i(-1, -1)
		var powerup_type := ""
		if game_instance and game_instance.powerups.size() > 0:
			var closest_dist := 999999
			for powerup in game_instance.powerups:
				var p_tile: Vector2i = grid_sampler.world_to_tile(powerup.position) if powerup else Vector2i(-1, -1)
				if p_tile != Vector2i(-1, -1):
					var dist: int = grid_sampler.get_manhattan_distance(current_tile, p_tile)
					if dist < closest_dist:
						closest_dist = dist
						nearest_powerup_pos = p_tile
						powerup_type = powerup.powerup_type if powerup.has_method("powerup_type") else "fire_up"
		
		var utility_result := utility_scorer.select_best_action(
			current_tile,
			player_ref.bomb_range if player_ref else 1,
			5.0,  # bot speed
			nearest_enemy_pos,
			nearest_enemy_id,
			nearest_powerup_pos,
			powerup_type,
			current_time_msec
		)
		
		# Apply utility decision to behavior tree scores
		var selected_action = utility_result["action"]
		var utility_score = utility_result["utility"]
		
		# Map utility actions to behavior tree nodes
		if selected_action == "get_powerup" and child == _collect_sequence:
			return base + utility_score
		elif selected_action in ["kick_snipe", "bait_panic", "nuisance_bomb"] and child == _attack_sequence:
			return base + utility_score
		elif selected_action == "establish_territory" and child == _ambush_node:
			return base + utility_score
	
	# SURVIVAL PRIORITY: Use new is_in_mortal_danger check
	if child == _escape_sequence and hazard_predictor and current_tile:
		var buffer: float = _personality_profile.get("danger_buffer", 0.1)
		if hazard_predictor.is_in_mortal_danger(current_tile, now, buffer):
			# CRITICAL DANGER - maximum priority
			base += 1000.0  # Overwhelming priority for survival
	elif child == _attack_sequence:
		var opponent = blackboard.get("nearest_opponent")
		if opponent == null:
			return 0.0
		
		# Don't attack if we're in mortal danger
		if hazard_predictor and hazard_predictor.is_in_mortal_danger(current_tile, now, 0.1):
			return 0.0  # Survival overrides aggression
		
		var tile: Vector2i = opponent.get("tile", current_tile)
		if tile != null and grid_sampler:
			var distance: int = grid_sampler.get_manhattan_distance(current_tile, tile)
			var base_aggression: float = max(0, 6 - distance) * _personality_profile.get("aggression", 0.5)
			
			# Use OpponentProfile to modify attack priority
			if game_instance and game_instance.ai_manager:
				var opp_id = opponent.get("peer_id", -999)
				if opp_id != -999:
					var profile = game_instance.ai_manager.get_opponent_profile(opp_id, "")
					
					# If opponent is aggressive (> 0.5), switch to defensive tactics
					if profile.aggression_score > 0.5:
						base_aggression *= 0.5  # Reduce attack priority against aggressive enemies
					
					# If opponent is panic bomber (> 0.7), use bait tactics
					if profile.panic_bomber_rating > 0.7:
						base_aggression *= 1.5  # Increase priority to bait them
			
			base += base_aggression
	elif child == _collect_sequence:
		if game_instance.powerups.size() == 0:
			return 0.0
		
		# Don't collect powerups if in mortal danger
		if hazard_predictor and hazard_predictor.is_in_mortal_danger(current_tile, now, 0.1):
			return 0.0  # Survival overrides greed
		
		base += 0.5
	elif child == _ambush_node:
		# Can't ambush if in danger
		if hazard_predictor and hazard_predictor.is_in_mortal_danger(current_tile, now, 0.1):
			return 0.0
		base += 0.2  # Low priority normally
	
	return base

## Opening Gambit State Machine - deterministic opening strategy
func _execute_opening_gambit(delta: float) -> void:
	var current_pos: Vector2i = player_ref.get_tile_position()
	var current_time_msec: int = Time.get_ticks_msec()
	
	match _current_state:
		BotState.ANALYZING_SPAWN:
			# T=0.00s: Analyze spawn pocket
			if opening_gambit.has_analyzed_spawn():
				_current_state = BotState.MOVING_TO_FIRST_BOMB
			else:
				_first_target = opening_gambit.analyse_spawn_pocket(current_pos, player_ref.bomb_range)
				print("[Bot ", player_ref.player_name, "] Opening analysis: target ", _first_target)
				_current_state = BotState.MOVING_TO_FIRST_BOMB
		
		BotState.MOVING_TO_FIRST_BOMB:
			# T=0.01s-0.2s: Move to optimal first bomb position
			if current_pos == _first_target:
				_current_state = BotState.PLANTING_FIRST_BOMB
			else:
				_move_to_tile(_first_target)
		
		BotState.PLANTING_FIRST_BOMB:
			# T=0.21s: Plant first bomb with safety check
			if not _has_planted_first_bomb and player_ref.can_place_bomb():
				if bomb_safety_checker != null:
					var is_safe: bool = bomb_safety_checker.can_safely_plant_bomb(
						current_pos, _first_target, player_ref.bomb_range, 
						5.0, current_time_msec
					)
					if is_safe:
						game_instance.place_bomb(player_ref)
						_has_planted_first_bomb = true
						print("[Bot ", player_ref.player_name, "] First bomb planted at ", _first_target)
						_current_state = BotState.WAITING_FOR_BLAST
					else:
						print("[Bot ", player_ref.player_name, "] First bomb unsafe, aborting opening gambit")
						_current_state = BotState.NORMAL
				else:
					# Fallback if safety checker not ready
					game_instance.place_bomb(player_ref)
					_has_planted_first_bomb = true
					_current_state = BotState.WAITING_FOR_BLAST
			else:
				# Can't plant yet, wait
				pass
		
		BotState.WAITING_FOR_BLAST:
			# T=0.22s-3.2s: Calculate chained action and wait for path to open
			var chain_result := opening_gambit.calculate_chained_action(
				current_pos, player_ref.bomb_range, current_time_msec
			)
			_second_target = chain_result["next_target"]
			
			# Check if path is available NOW
			if chain_result["can_path_now"]:
				print("[Bot ", player_ref.player_name, "] Path opened! Farming to ", _second_target)
				_current_state = BotState.FARMING
			else:
				# Path blocked, stay in safe spawn pocket
				# Move to spawn position if not already there
				var spawn_pos := opening_gambit.get_first_target()  # Use first target as reference
				# Actually move towards spawn (where we came from)
				# For now, stay still in the waiting room
				pass
		
		BotState.FARMING:
			# T=3.21s+: Execute chained bomb placement
			if current_pos == _second_target:
				# Arrived at second target, plant bomb
				if player_ref.can_place_bomb():
					if bomb_safety_checker != null:
						var is_safe: bool = bomb_safety_checker.can_safely_plant_bomb(
							current_pos, _second_target, player_ref.bomb_range,
							5.0, current_time_msec
						)
						if is_safe:
							game_instance.place_bomb(player_ref)
							print("[Bot ", player_ref.player_name, "] Second bomb planted, entering normal mode")
					else:
						game_instance.place_bomb(player_ref)
				
				# Transition to normal behavior tree after second bomb
				_current_state = BotState.NORMAL
			else:
				# Move to second target
				_move_to_tile(_second_target)

## Simple tile movement helper for opening gambit
func _move_to_tile(target: Vector2i) -> void:
	if player_ref == null:
		return
	
	var current_pos: Vector2i = player_ref.get_tile_position()
	var delta: Vector2i = target - current_pos
	
	# Simple cardinal movement
	var axis := Vector2.ZERO
	if abs(delta.x) > abs(delta.y):
		axis = Vector2(sign(delta.x), 0.0)
	else:
		axis = Vector2(0.0, sign(delta.y))
	
	player_ref.set_input(axis.x, axis.y)

func _on_player_removed() -> void:
	player_ref = null
	queue_free()

