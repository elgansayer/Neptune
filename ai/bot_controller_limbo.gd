extends Node
class_name ServerBotControllerLimbo

## LimboAI-powered bot controller for authoritative server AI
## Replaces custom BT system with LimboAI's BTPlayer

const AIPersonalitiesConfig = preload("res://shared/ai/config/personalities.gd")

# Game references
var game_instance
var personality := "BALANCED"
var player_ref
var grid_sampler
var hazard_predictor
var opponent_tracker
var bomb_planner

# LimboAI components
var bt_player: BTPlayer
var _personality_profile := {}
var _decision_interval := 0.1
var _decision_accumulator := 0.0

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
	
	# Setup LimboAI BTPlayer
	_setup_limbo_bt()
	
	if player_ref:
		player_ref.tree_exited.connect(_on_player_removed, Object.CONNECT_ONE_SHOT)

func _setup_limbo_bt() -> void:
	# Create BTPlayer node
	bt_player = BTPlayer.new()
	add_child(bt_player)
	
	# Build behavior tree programmatically
	# (In production, load from .tres resource file instead)
	var root = _build_behavior_tree_for_personality(personality)
	
	# Create BehaviorTree resource
	var behavior_tree = BehaviorTree.new()
	behavior_tree.root_task = root
	bt_player.behavior_tree = behavior_tree
	
	# Setup blackboard with initial values
	_setup_blackboard()

func _build_behavior_tree_for_personality(personality_name: String) -> BTTask:
	# Root selector - picks highest priority sequence
	var root = BTSelector.new()
	
	# Escape sequence (highest priority when in danger)
	var escape_seq = BTSequence.new()
	
	var is_in_danger = preload("res://ai/tasks/conditions/bt_is_in_danger.gd").new()
	is_in_danger.danger_buffer = _personality_profile.get("danger_buffer", 1.0)
	is_in_danger.evaluate_all_threats = true
	escape_seq.add_child(is_in_danger)
	
	var find_escape = preload("res://ai/tasks/actions/bt_find_escape_route.gd").new()
	find_escape.escape_radius = _personality_profile.get("escape_radius", 8)
	escape_seq.add_child(find_escape)
	
	var move_to_safety = preload("res://ai/tasks/actions/bt_move_to_cell.gd").new()
	escape_seq.add_child(move_to_safety)
	
	root.add_child(escape_seq)
	
	# Attack sequence (when opponent nearby)
	if _personality_profile.get("attack_bias", 1.0) > 0.3:
		var attack_seq = BTSequence.new()
		
		# TODO: Add BTIsOpponentNearby condition
		# For now, just move and place bomb
		var move_to_opponent = preload("res://ai/tasks/actions/bt_move_to_cell.gd").new()
		attack_seq.add_child(move_to_opponent)
		
		var place_bomb = preload("res://ai/tasks/actions/bt_place_bomb.gd").new()
		attack_seq.add_child(place_bomb)
		
		root.add_child(attack_seq)
	
	# Collect powerup sequence
	if _personality_profile.get("powerup_bias", 0.8) > 0.3:
		var collect_seq = BTSequence.new()
		
		# TODO: Add BTIsPowerupAvailable condition
		var move_to_powerup = preload("res://ai/tasks/actions/bt_move_to_cell.gd").new()
		collect_seq.add_child(move_to_powerup)
		
		root.add_child(collect_seq)
	
	# Default: Idle/wait
	# TODO: Add BTWaitAmbush or similar fallback action
	
	return root

func _setup_blackboard() -> void:
	if not bt_player:
		return
	
	var bb = bt_player.blackboard
	bb.set_var("game_instance", game_instance)
	bb.set_var("player", player_ref)
	bb.set_var("grid_sampler", grid_sampler)
	bb.set_var("hazard_predictor", hazard_predictor)
	bb.set_var("opponent_tracker", opponent_tracker)
	bb.set_var("bomb_planner", bomb_planner)
	bb.set_var("personality", _personality_profile)
	bb.set_var("ai_manager", game_instance.ai_manager if game_instance else null)

func _physics_process(delta: float) -> void:
	if not is_instance_valid(player_ref) or player_ref.is_dead:
		return
	if not bt_player:
		return
	
	_decision_accumulator += delta
	if _decision_accumulator < _decision_interval:
		return
	_decision_accumulator = 0.0
	
	# Update blackboard with current game state
	_update_blackboard()
	
	# LimboAI automatically ticks the BT
	# No manual tick needed - it processes in its own _process
	
	# Apply outputs from blackboard to player
	_apply_outputs()

func _update_blackboard() -> void:
	if not bt_player:
		return
	
	var bb = bt_player.blackboard
	
	# Update dynamic values
	bb.set_var("time", Time.get_ticks_msec() / 1000.0)
	bb.set_var("current_tile", player_ref.get_tile_position())
	bb.set_var("current_world", player_ref.position)
	
	# Update opponent tracking
	var nearest = opponent_tracker.get_nearest_opponent(player_ref.position)
	bb.set_var("nearest_opponent", nearest)
	if nearest:
		bb.set_var("opponent_tile", nearest.get("tile"))
	else:
		bb.set_var("opponent_tile", null)
	
	# Reset output variables (will be set by BT actions)
	bb.set_var("move_vector", Vector2.ZERO)
	bb.set_var("request_bomb", false)

func _apply_outputs() -> void:
	if not is_instance_valid(player_ref) or not bt_player:
		return
	
	var bb = bt_player.blackboard
	
	# Apply movement from blackboard
	var desired: Vector2 = bb.get_var("move_vector", Vector2.ZERO)
	var axis := Vector2.ZERO
	if desired.length() > 0.05:
		if abs(desired.x) > abs(desired.y):
			axis = Vector2(sign(desired.x), 0.0)
		else:
			axis = Vector2(0.0, sign(desired.y))
	player_ref.set_input(axis.x, axis.y)
	
	# Apply bomb placement
	if bb.get_var("request_bomb", false):
		game_instance.place_bomb(player_ref)
		bb.set_var("request_bomb", false)

func _on_player_removed() -> void:
	player_ref = null
	if bt_player:
		bt_player.queue_free()
	queue_free()
