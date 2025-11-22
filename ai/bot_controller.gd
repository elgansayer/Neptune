extends Node
class_name ServerBotController

const AIPersonalitiesConfig = preload("res://shared/ai/config/personalities.gd")

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
var _limbo_player # BTPlayer instance
var _limbo_blackboard # Blackboard instance
var _limbo_tree # BehaviorTree resource

var bomb_safety_checker # Time-aware BFS suicide check

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

func _physics_process(delta: float) -> void:
	if not is_instance_valid(player_ref) or player_ref.is_dead:
		return
	
	# Continuous farming spot broadcasting for visualization
	# Broadcast every 60 frames (~1 second at 60 FPS)
	# Note: BTFindFarmingSpot now handles broadcasting directly
	pass
	
	# Decision tick throttling
	_decision_accumulator += delta
	if _decision_accumulator < _decision_interval:
		return
	_decision_accumulator = 0.0
	
	# Tick LimboAI tree
	if Engine.get_physics_frames() % 60 == 0:
		var danger = _limbo_blackboard.get_var("in_danger", false)
		var target = _limbo_blackboard.get_var("target_cell", null)
		print("[BotController] Heartbeat - Active: %s | Danger: %s | Target: %s | Player: %s" % [is_instance_valid(_limbo_player), danger, target, player_ref.name if is_instance_valid(player_ref) else "Invalid"])
	_tick_limbo(delta)

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
		_limbo_player.set("agent", player_ref) # Direct node reference
	else:
		_limbo_player.set("agent", self)
	
	add_child(_limbo_player)
	
	# OPTION A: Load pre-built tree resource (editable in LimboAI visual editor)
	if ResourceLoader.exists("res://ai/trees/bot_default.tres"):
		_limbo_player.set_behavior_tree(_limbo_tree)
		
		# CRITICAL: Set update mode to PHYSICS_PROCESS so tree re-evaluates every frame
		# Default is IDLE (0) which caches result after first evaluation
		# PHYSICS_PROCESS (1) = re-evaluate tree every physics frame
		_limbo_player.set("update_mode", 1) # BTPlayer.PHYSICS_PROCESS
		_limbo_player.set("process_mode", Node.PROCESS_MODE_INHERIT) # Ensure not disabled
		_limbo_player.set("active", true) # Explicitly activate
		
		print("[BotController] Loaded Limbo tree from resource for ", player_ref.player_name if player_ref else "bot")
		print("[BotController] BTPlayer configured: update_mode=", _limbo_player.get("update_mode"), " process_mode=", _limbo_player.get("process_mode"), " active=", _limbo_player.get("active"))
		
		# CRITICAL: Populate blackboard after loading tree
		_update_limbo_blackboard()
		
		# CRITICAL: Restart tree to ensure it starts fresh
		_limbo_player.restart()
		print("[BotController] BTPlayer restarted and ready")
		return
	
	push_error("[BotController] Critical Error: res://ai/trees/bot_default.tres not found! Bot cannot function.")
	
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
	
	# Ensure safety checker is configured (handle race condition where manager might not have configured it yet)
	if bomb_safety_checker and game_instance and game_instance.ai_manager:
		# It's safe to call configure multiple times
		bomb_safety_checker.configure(game_instance.ai_manager, grid_sampler)
	
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
		"bot_state": "LIMBO_AI",
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
