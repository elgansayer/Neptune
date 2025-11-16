extends Node
class_name ServerBotController

const BehaviorTreeRunner = preload("res://shared/ai/behavior_tree/bt_runner.gd")
const LegacyBTSequence = preload("res://shared/ai/behavior_tree/nodes/sequence.gd")
const LegacyBTUtilitySelector = preload("res://shared/ai/behavior_tree/nodes/utility_selector.gd")
const BTEscapeNode = preload("res://shared/ai/behavior_tree/nodes/leaf_find_escape.gd")
const BTMoveToNode = preload("res://shared/ai/behavior_tree/nodes/leaf_move_to.gd")
const BTCollectPowerUpNode = preload("res://shared/ai/behavior_tree/nodes/leaf_collect_powerup.gd")
const BTPlaceBombNode = preload("res://shared/ai/behavior_tree/nodes/leaf_place_bomb.gd")
const BTWaitAmbushNode = preload("res://shared/ai/behavior_tree/nodes/leaf_wait_ambush.gd")
const BTChaseOpponentNode = preload("res://shared/ai/behavior_tree/nodes/leaf_chase_opponent.gd")
const AIPersonalitiesConfig = preload("res://shared/ai/config/personalities.gd")

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

func configure(instance, player, personality_name: String,
		sampler, predictor,
		tracker, planner) -> void:
	game_instance = instance
	player_ref = player
	grid_sampler = sampler
	hazard_predictor = predictor
	opponent_tracker = tracker
	bomb_planner = planner
	personality = personality_name
	_personality_profile = AIPersonalitiesConfig.get_profile(personality_name)
	_decision_interval = _personality_profile.get("decision_interval", 0.1)
	_build_behavior_tree()
	if player_ref:
		player_ref.tree_exited.connect(_on_player_removed, Object.CONNECT_ONE_SHOT)

func _build_behavior_tree() -> void:
	_escape_sequence = LegacyBTSequence.new()
	_escape_sequence.children = [BTEscapeNode.new(), BTMoveToNode.new()]
	_attack_sequence = LegacyBTSequence.new()
	_attack_sequence.children = [BTChaseOpponentNode.new(), BTMoveToNode.new(), BTPlaceBombNode.new()]
	_collect_sequence = LegacyBTSequence.new()
	_collect_sequence.children = [BTCollectPowerUpNode.new(), BTMoveToNode.new()]
	_ambush_node = BTWaitAmbushNode.new()
	var utility_selector = LegacyBTUtilitySelector.new()
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
	_blackboard["player"] = player_ref
	_blackboard["personality"] = _personality_profile
	_blackboard["time"] = Time.get_ticks_msec() / 1000.0
	_blackboard["danger_buffer"] = _personality_profile.get("danger_buffer", 1.0)
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
	if child == _escape_sequence and hazard_predictor and current_tile:
		if not hazard_predictor.is_tile_safe(current_tile, now, _personality_profile.get("danger_buffer", 1.0)):
			base += 8.0
	elif child == _attack_sequence:
		var opponent = blackboard.get("nearest_opponent")
		if opponent == null:
			return 0.0
		var tile: Vector2i = opponent.get("tile", current_tile)
		if tile != null and grid_sampler:
			var distance = grid_sampler.get_manhattan_distance(current_tile, tile)
			base += max(0, 6 - distance) * _personality_profile.get("aggression", 0.5)
	elif child == _collect_sequence:
		if game_instance.powerups.size() == 0:
			return 0.0
		base += 0.5
	elif child == _ambush_node:
		if hazard_predictor and current_tile and not hazard_predictor.is_tile_safe(current_tile, now, 0.2):
			base -= 1.0
	return base

func _on_player_removed() -> void:
	player_ref = null
	queue_free()
