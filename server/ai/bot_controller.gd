extends Node
class_name ServerBotController

const AIPersonalitiesConfig = preload("res://shared/ai/config/personalities.gd")
const OpeningGambit = preload("res://shared/ai/planning/opening_gambit.gd")
const UtilityScorer = preload("res://shared/ai/decision/utility_scorer.gd")

## LimboAI-powered bot controller that simulates authoritative inputs for AI players.

var game_instance
var personality := "BALANCED"
var player_ref
var grid_sampler
var hazard_predictor
var opponent_tracker
var bomb_planner

var _personality_profile := {}
var _decision_interval := 0.1
var _decision_accumulator := 0.0

# Limbo AI integration
var _limbo_player  # BTPlayer instance
var _limbo_blackboard  # Blackboard instance
var _limbo_tree  # BehaviorTree resource

var bomb_safety_checker  # New: time-aware BFS suicide check
var opening_gambit: OpeningGambit  # Opening strategy planner
var utility_scorer: UtilityScorer  # Mathematical (Reward * P_Success) - (Risk * P_Failure)

# State machine for opening gambit
enum BotState { ANALYZING_SPAWN, MOVING_TO_FIRST_BOMB, PLANTING_FIRST_BOMB, WAITING_FOR_BLAST, FARMING, NORMAL }
var _current_state: BotState = BotState.NORMAL  # Start in NORMAL to use behavior tree immediately
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
	
	# Store game_instance for BTPlayer scene_root_hint
	# (needed before _build_limbo_tree is called)
	
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
	
	# LimboAI is now the only BT system
	if ClassDB.class_exists("BTPlayer"):
		print("[BotController] Building LimboAI tree for ", player_ref.player_name if player_ref else "bot")
		_build_limbo_tree()
	else:
		push_error("[BotController] LimboAI not available! Bot will be disabled.")
	
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

func _physics_process(delta: float) -> void:
	if not is_instance_valid(player_ref) or player_ref.is_dead:
		return
	
	# Automatic farming spot broadcasting disabled - use F8 key to manually trigger
	# if Engine.get_physics_frames() % 60 == 0:
	# 	_broadcast_farming_evaluation()
	
	# Opening Gambit State Machine (overrides normal behavior tree during opening)
	if _current_state != BotState.NORMAL:
		_execute_opening_gambit(delta)
		return
	
	# Decision tick throttling
	_decision_accumulator += delta
	if _decision_accumulator < _decision_interval:
		return
	_decision_accumulator = 0.0
	
	# Tick LimboAI tree
	_tick_limbo(delta)

## Opening Gambit State Machine - deterministic opening strategy
func _execute_opening_gambit(_delta: float) -> void:
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
				# Path blocked, stay in safe spawn pocket waiting for explosion
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

func _build_limbo_tree() -> void:
	"""Build LimboAI behavior tree using custom nodes"""
	if not ClassDB.class_exists("BTPlayer"):
		push_warning("[BotController] LimboAI not available, cannot build tree")
		return
	
	# Create BTPlayer node
	var limbo_player_node = ClassDB.instantiate("BTPlayer")
	_limbo_player = limbo_player_node
	
	# Create Blackboard FIRST (before any initialization)
	var limbo_bb = ClassDB.instantiate("Blackboard")
	_limbo_blackboard = limbo_bb
	_limbo_player.set_blackboard(_limbo_blackboard)
	
	# CRITICAL: BTPlayer needs scene_root to initialize. It tries get_owner() first, then scene_root_hint.
	# Since this controller is dynamically created and added to bot_manager (not part of a saved scene),
	# we must manually set scene_root_hint to game_instance BEFORE add_child().
	# Reference: bt_player.cpp:41 "_get_scene_root() returns scene_root_hint ? scene_root_hint : get_owner()"
	if game_instance and is_instance_valid(game_instance):
		_limbo_player.call("set_scene_root_hint", game_instance)
	
	# Set the agent node - this is what BTPlayer controls
	if player_ref and is_instance_valid(player_ref):
		_limbo_player.set("agent", player_ref)  # Direct node reference
	else:
		_limbo_player.set("agent", self)
	
	add_child(_limbo_player)
	
	# OPTION A: Load pre-built tree resource (editable in LimboAI visual editor)
	if ResourceLoader.exists("res://ai/trees/bot_default.tres"):
		_limbo_tree = ResourceLoader.load("res://ai/trees/bot_default.tres")
		_limbo_player.set_behavior_tree(_limbo_tree)
		print("[BotController] Loaded Limbo tree from resource for ", player_ref.player_name if player_ref else "bot")
		
		# CRITICAL: Populate blackboard after loading tree
		_update_limbo_blackboard()
		return
	
	# OPTION B: Build tree programmatically (fallback if resource missing)
	print("[BotController] Building Limbo tree programmatically for ", player_ref.player_name if player_ref else "bot")
	var limbo_tree_res = ClassDB.instantiate("BehaviorTree")
	_limbo_tree = limbo_tree_res
	
	# Build tree structure: BTSelector root with priority sequences
	var root_selector = ClassDB.instantiate("BTSelector")
	
	# Sequence 1: ESCAPE (highest priority)
	var escape_seq = ClassDB.instantiate("BTSequence")
	var is_in_danger = load("res://ai/tasks/conditions/bt_is_in_danger.gd").new()
	is_in_danger.danger_buffer = _personality_profile.get("danger_buffer", 1.0)
	is_in_danger.check_immediate = false
	var find_escape = load("res://ai/tasks/actions/bt_find_escape_route.gd").new()
	find_escape.escape_radius = _personality_profile.get("escape_radius", 8)
	find_escape.target_cell_var = &"target_cell"
	var move_to = load("res://ai/tasks/actions/bt_move_to_cell.gd").new()
	move_to.cell_var = &"target_cell"
	move_to.reach_threshold = 0.3
	
	# Escape sequence expects: BTIsInDanger -> BTFindEscapeRoute -> BTMoveToCell
	# Note: BTSelector/BTSequence use add_child for composition
	escape_seq.call("add_child", is_in_danger)
	escape_seq.call("add_child", find_escape)
	escape_seq.call("add_child", move_to)
	
	# Sequence 2: ATTACK (if opponent exists and not in danger)
	# Simplified for now: just place bomb + move (no opponent check condition yet)
	var attack_seq = ClassDB.instantiate("BTSequence")
	var place_bomb = load("res://ai/tasks/actions/bt_place_bomb.gd").new()
	place_bomb.check_capacity = true
	place_bomb.check_existing = true
	var retreat_after_bomb = load("res://ai/tasks/actions/bt_find_escape_route.gd").new()
	retreat_after_bomb.escape_radius = 6
	retreat_after_bomb.target_cell_var = &"target_cell"
	var move_retreat = load("res://ai/tasks/actions/bt_move_to_cell.gd").new()
	move_retreat.cell_var = &"target_cell"
	attack_seq.call("add_child", place_bomb)
	attack_seq.call("add_child", retreat_after_bomb)
	attack_seq.call("add_child", move_retreat)
	
	# Sequence 3: COLLECT (low priority, placeholder for now)
	# TODO: Add BTHasPowerup check and pathfinding to powerup
	var collect_seq = ClassDB.instantiate("BTSequence")
	# Placeholder: just move to a cell if target_powerup is set
	var move_collect = load("res://ai/tasks/actions/bt_move_to_cell.gd").new()
	move_collect.cell_var = &"target_powerup_cell"
	collect_seq.call("add_child", move_collect)
	
	# Assemble selector
	root_selector.call("add_child", escape_seq)
	root_selector.call("add_child", attack_seq)
	root_selector.call("add_child", collect_seq)
	
	# Set root
	_limbo_tree.call("set_root_task", root_selector)
	_limbo_player.set_behavior_tree(_limbo_tree)
	
	# CRITICAL: Populate blackboard AFTER setting behavior tree
	# When set_behavior_tree() is called, BTPlayer creates a new BTInstance with a fresh blackboard
	# We need to populate it before the first tick
	_update_limbo_blackboard()
	
	print("[BotController] Limbo tree built for ", player_ref.player_name if player_ref else "bot")

func _update_limbo_blackboard() -> void:
	"""Populate Limbo blackboard with current game state"""
	if not _limbo_blackboard:
		return
	
	# Entity references
	_limbo_blackboard.set_var("player", player_ref)
	_limbo_blackboard.set_var("game_instance", game_instance)
	_limbo_blackboard.set_var("ai_manager", game_instance.ai_manager if game_instance else null)
	
	# Perception systems
	_limbo_blackboard.set_var("grid_sampler", grid_sampler)
	_limbo_blackboard.set_var("hazard_predictor", hazard_predictor)
	_limbo_blackboard.set_var("opponent_tracker", opponent_tracker)
	_limbo_blackboard.set_var("bomb_planner", bomb_planner)
	_limbo_blackboard.set_var("bomb_safety_checker", bomb_safety_checker)
	
	# State
	_limbo_blackboard.set_var("current_tile", player_ref.get_tile_position() if player_ref else Vector2i.ZERO)
	_limbo_blackboard.set_var("time", Time.get_ticks_msec() / 1000.0)
	_limbo_blackboard.set_var("danger_buffer", _personality_profile.get("danger_buffer", 0.1))
	_limbo_blackboard.set_var("escape_radius", _personality_profile.get("escape_radius", 8))
	
	# Optional state variables (initialized to prevent C++ errors when reading before writing)
	if not _limbo_blackboard.has_var("in_danger"):
		_limbo_blackboard.set_var("in_danger", false)
	if not _limbo_blackboard.has_var("danger_tile"):
		_limbo_blackboard.set_var("danger_tile", null)
	if not _limbo_blackboard.has_var("target_cell"):
		_limbo_blackboard.set_var("target_cell", null)
	if not _limbo_blackboard.has_var("escape_route_found"):
		_limbo_blackboard.set_var("escape_route_found", false)
	
	# Opponent tracking
	var nearest = opponent_tracker.get_nearest_opponent(player_ref.position) if player_ref else null
	_limbo_blackboard.set_var("nearest_opponent", nearest)
	if nearest:
		_limbo_blackboard.set_var("opponent_tile", nearest.get("tile"))
	else:
		_limbo_blackboard.set_var("opponent_tile", null)
	
	# Powerup tracking (simplified)
	if game_instance and game_instance.powerups.size() > 0:
		var closest_powerup = game_instance.powerups[0]
		var powerup_tile = grid_sampler.world_to_tile(closest_powerup.position) if closest_powerup else Vector2i(-1, -1)
		_limbo_blackboard.set_var("target_powerup_cell", powerup_tile)
	else:
		_limbo_blackboard.set_var("target_powerup_cell", null)

func _tick_limbo(delta: float) -> void:
	"""Execute Limbo BT tick"""
	if not _limbo_player or not _limbo_blackboard:
		return
	
	# Update blackboard from game state
	_update_limbo_blackboard()
	
	# Tick the BTPlayer (automatically uses assigned blackboard)
	_limbo_player.update(delta)
	
	# Read outputs from blackboard (nodes write movement intent here)
	# Note: Our custom nodes call player.set_input directly, so no additional apply needed
	# But we can read diagnostic vars for debug payload
	# (Actual movement handled by BTMoveToCell node directly)

func get_debug_payload() -> Dictionary:
	"""Generate debug payload for streaming to clients"""
	if not is_instance_valid(player_ref):
		return {}
	
	var payload := {
		"peer_id": player_ref.peer_id,
		"player_name": player_ref.player_name,
		"current_tile": player_ref.get_tile_position(),
		"bot_state": BotState.keys()[_current_state],
		"plan_type": "limbo_tree",
	}
	
	# LimboAI blackboard debug data
	if _limbo_blackboard:
		payload["in_danger"] = _limbo_blackboard.get_var("in_danger", false)
		payload["danger_tile"] = _limbo_blackboard.get_var("danger_tile", null)
		payload["escape_route_found"] = _limbo_blackboard.get_var("escape_route_found", false)
		payload["target_cell"] = _limbo_blackboard.get_var("target_cell", null)
	
	return payload

func _on_player_removed() -> void:
	player_ref = null
	queue_free()

func test_farming_spot() -> void:
	print("[BotController] TEST: Executing manual farming spot search")
	if player_ref == null:
		print("[BotController] TEST: No player ref")
		return
	
	if game_instance == null or grid_sampler == null or bomb_safety_checker == null:
		print("[BotController] TEST: Missing required components")
		return
	
	# Directly call the farming spot evaluation logic
	var current_tile = player_ref.get_tile_position()
	var bomb_range = player_ref.bomb_range
	var search_radius = 5
	
	print("[BotController] TEST: Searching from ", current_tile, " radius=", search_radius)
	
	var safety_eval := {}
	var candidates_checked := 0
	
	for dx in range(-search_radius, search_radius + 1):
		for dy in range(-search_radius, search_radius + 1):
			if dx == 0 and dy == 0:
				continue
			
			var check_tile = current_tile + Vector2i(dx, dy)
			candidates_checked += 1
			
			# Check if walkable
			if not grid_sampler.is_tile_walkable(check_tile):
				continue
			
			# Count soft blocks in range
			var soft_blocks = 0
			for bx in range(-bomb_range, bomb_range + 1):
				for by in range(-bomb_range, bomb_range + 1):
					if abs(bx) + abs(by) > bomb_range:
						continue
					var block_tile = check_tile + Vector2i(bx, by)
					if grid_sampler.has_soft_block(block_tile):
						soft_blocks += 1
			
			if soft_blocks == 0:
				continue
			
			# Check safety
			var safety_result = bomb_safety_checker.is_bomb_placement_safe(check_tile, player_ref)
			if not safety_result.safe:
				continue
			
			# Calculate score
			var margin = safety_result.get("margin_ms", 0.0)
			var escape_distance = safety_result.get("escape_distance", 999)
			
			var safety_multiplier = 1.0
			if escape_distance == 1:
				safety_multiplier *= 1.5
			elif escape_distance == 2:
				safety_multiplier *= 1.2
			elif escape_distance >= 5:
				safety_multiplier *= 0.7
			
			if margin > 1000.0:
				safety_multiplier *= 1.2
			elif margin < 800.0:
				safety_multiplier *= 0.8
			
			var damage_score = soft_blocks * 10.0
			var final_score = damage_score * safety_multiplier
			var distance = abs(dx) + abs(dy)
			final_score -= distance * 0.3
			
			# Add to visualization data
			var tile_key = "%d,%d" % [check_tile.x, check_tile.y]
			var status = 2 if margin > 800.0 else 1
			safety_eval[tile_key] = {
				"status": status,
				"soft_blocks": soft_blocks,
				"margin_ms": margin,
				"escape_distance": escape_distance,
				"final_score": final_score
			}
	
	print("[BotController] TEST: Checked %d candidates, found %d valid spots" % [candidates_checked, safety_eval.size()])
	
	# Broadcast to all clients
	if not safety_eval.is_empty():
		_broadcast_safety_to_clients(safety_eval)
	else:
		print("[BotController] TEST: No safe farming spots found")


func _broadcast_safety_to_clients(safety_data: Dictionary) -> void:
	"""Send safety evaluation to all connected clients"""
	if not game_instance:
		print("[BotController] Cannot broadcast: no game_instance")
		return
	
	# Get the client game view node and call RPC on it
	# Since we're on the server, we need to call the client's game_view
	print("[BotController] Broadcasting %d tiles to clients via RPC" % safety_data.size())
	
	# Use the multiplayer's RPC system to call bomb_safety_update on all clients
	if game_instance.has_method("rpc"):
		game_instance.rpc("bomb_safety_update", safety_data)


## Continuous farming spot evaluation broadcast for visualization
func _broadcast_farming_evaluation() -> void:
	if not is_instance_valid(player_ref):
		print("[BotController] Broadcast skipped: player_ref invalid")
		return
	if not is_instance_valid(game_instance):
		print("[BotController] Broadcast skipped: game_instance invalid")
		return
	
	# Dynamically load and instantiate the farming spot task
	var BTFindFarmingSpotScript = load("res://ai/tasks/actions/bt_find_farming_spot.gd")
	if not BTFindFarmingSpotScript:
		print("[BotController] Failed to load farming spot script")
		return
	
	var task = BTFindFarmingSpotScript.new()
	task.target_cell_var = "target_cell"
	task.broadcast_safety = true
	task.debug_logging = true
	task.blackboard = _limbo_blackboard
	
	print("[BotController] Task created, blackboard valid: ", _limbo_blackboard != null)
	
	# Use the existing blackboard with all required variables
	if _limbo_blackboard != null:
		print("[BotController] Calling _tick...")
		var result = task._tick(0.016)
		print("[BotController] Broadcast complete, result: ", result)
	else:
		print("[BotController] Broadcast skipped: blackboard not initialized")


