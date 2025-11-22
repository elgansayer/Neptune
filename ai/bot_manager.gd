extends Node
class_name ServerBotManager

# CRITICAL: Process BEFORE player entities to set input before their _physics_process
# Negative priority means this runs first
const PROCESS_PRIORITY = 200

# LimboAI components - ONLY system used for AI
# Note: BehaviorTree and BTPlayer are native classes, accessed via ClassDB

const GridSamplerScript = preload("res://shared/ai/perception/grid_sampler.gd")
const HazardPredictorScript = preload("res://shared/ai/perception/hazard_predictor.gd")
const OpponentTrackerScript = preload("res://shared/ai/perception/opponent_tracker.gd")
const BombPlannerScript = preload("res://shared/ai/perception/bomb_planner.gd")
const BombSafetyCheckerScript = preload("res://shared/ai/planning/bomb_safety_checker.gd")

var game_instance
var _bot_players: Dictionary = {} # peer_id -> BTPlayer
var grid_sampler
var hazard_predictor
var opponent_tracker
var bomb_planner
var bomb_safety_checker
var next_bot_peer_id := -1
var auto_spawned := false
var bot_behavior_tree # BehaviorTree resource

const DEFAULT_PERSONALITY := "BALANCED"
var auto_spawn_count := 3

func _ready() -> void:
	# Set process priority to run AFTER game instance (100)
	# Higher numbers run later
	process_priority = PROCESS_PRIORITY
	print("[BotManager] Process priority set to ", PROCESS_PRIORITY)

func configure(instance) -> void:
	game_instance = instance
	
	# Load LimboAI behavior tree (force reload, ignore cache)
	bot_behavior_tree = ResourceLoader.load("res://ai/trees/bot_default.tres", "", ResourceLoader.CACHE_MODE_IGNORE)
	if not bot_behavior_tree:
		push_error("[BotManager] Failed to load bot_default.tres!")
		return
	print("[BotManager] Loaded bot_default.tres (cache ignored)")
	
	grid_sampler = GridSamplerScript.new()
	grid_sampler.configure(game_instance, null, GameConfig.TILE_SIZE)
	hazard_predictor = HazardPredictorScript.new()
	hazard_predictor.configure(game_instance, grid_sampler)
	opponent_tracker = OpponentTrackerScript.new()
	bomb_planner = BombPlannerScript.new()
	bomb_planner.configure(grid_sampler, hazard_predictor)
	
	bomb_safety_checker = BombSafetyCheckerScript.new()
	
	call_deferred("_configure_safety_checker")
	
	if auto_spawn_count > 0:
		print("[BotManager] Queuing auto-spawn for %d bots" % auto_spawn_count)
		call_deferred("_auto_spawn_bots")

func _configure_safety_checker() -> void:
	if game_instance != null and game_instance.ai_manager != null:
		bomb_safety_checker.configure(game_instance.ai_manager, grid_sampler)
		bomb_safety_checker.debug_logging = true
		print("[BotManager] BombSafetyChecker configured with AIManager (debug=ON)")

func _auto_spawn_bots() -> void:
	if auto_spawned:
		return
	auto_spawned = true
	print("[BotManager] Auto-spawning %d bots" % auto_spawn_count)
	spawn_bots(auto_spawn_count, DEFAULT_PERSONALITY)

func _physics_process(delta: float) -> void:
	if game_instance == null:
		return
	
	# Handle match_active state for all bots
	var should_be_active = game_instance.match_active
	for peer_id in _bot_players:
		var bt_player = _bot_players[peer_id]
		if is_instance_valid(bt_player):
			var current_active = bt_player.get("active")
			if current_active != should_be_active:
				bt_player.set("active", should_be_active)
	
	# Don't update bots during countdown
	if not game_instance.match_active:
		return
	
	hazard_predictor.refresh(Time.get_ticks_msec() / 1000.0)
	opponent_tracker.update_from_players(game_instance.players.values())
	
	# Debug log every 120 frames (~2 seconds)
	if Engine.get_physics_frames() % 120 == 0 and not _bot_players.is_empty():
		print("[BotManager] _physics_process running, ", _bot_players.size(), " bots active")
		for peer_id in _bot_players:
			var bt_player = _bot_players[peer_id]
			if is_instance_valid(bt_player):
				print("  - BTPlayer active=", bt_player.get("active"), " update_mode=", bt_player.get("update_mode"))
	
	# Update blackboard values for each bot before BTPlayer auto-updates
	for peer_id in _bot_players:
		var bt_player = _bot_players[peer_id]
		if is_instance_valid(bt_player):
			var blackboard = bt_player.get_blackboard()
			if blackboard:
				var player_ref = blackboard.get_var("player", null)
				if is_instance_valid(player_ref):
					# Update dynamic blackboard values
					blackboard.set_var("current_tile", player_ref.get_tile_position())
					blackboard.set_var("time", Time.get_ticks_msec() / 1000.0)
					
					# WORKAROUND: Manual update since BTPlayer doesn't auto-update (update_mode stuck at 0)
					# Call update() to tick the tree once
					bt_player.call("update", delta)
					
					# CRITICAL: Unconditionally restart tree to force re-evaluation
					# This makes BTRepeatUntilFailure work even with manual updates
					bt_player.call("restart")
	
	# Update opponent intelligence profiles
	if game_instance.ai_manager != null:
		var bot_positions := {}
		for peer_id in _bot_players:
			var bt_player = _bot_players[peer_id]
			if is_instance_valid(bt_player):
				var blackboard = bt_player.get_blackboard()
				if blackboard:
					var player_ref = blackboard.get_var("player", null)
					if is_instance_valid(player_ref):
						bot_positions[peer_id] = player_ref.get_tile_position()
		
		game_instance.ai_manager.update_opponent_intel(bot_positions, game_instance.players, delta)

func spawn_bots(count: int, personality: String = DEFAULT_PERSONALITY) -> void:
	for i in range(count):
		spawn_bot(personality)

func spawn_bot(personality: String = DEFAULT_PERSONALITY) -> void:
	if game_instance == null:
		push_warning("[BotManager] GameInstance not assigned yet")
		return
	
	var peer_id = next_bot_peer_id
	next_bot_peer_id -= 1
	
	game_instance.add_player(peer_id, "%s_Bot_%d" % [personality.capitalize(), abs(peer_id)], Vector2.ZERO, true, personality)
	if not game_instance.players.has(peer_id):
		push_warning("[BotManager] Failed to spawn bot player for peer id %s" % peer_id)
		return
	
	var player = game_instance.players[peer_id]
	print("[BotManager] Spawned bot %s (peer %d)" % [player.player_name, peer_id])
	
	# Create BTPlayer using ClassDB (native LimboAI class)
	var bt_player = ClassDB.instantiate("BTPlayer")
	bt_player.name = "BTPlayer_%d" % abs(peer_id)
	
	# Set behavior tree FIRST (this includes the blackboard_plan)
	bt_player.set("behavior_tree", bot_behavior_tree)
	
	# Set agent
	bt_player.set("agent", player)
	
	# CRITICAL: Must set scene_root_hint BEFORE add_child
	# because BTPlayer._enter_tree() needs it during initialization
	# NOTE: .owner can't be set before add_child, so use scene_root_hint property
	var scene_root = get_tree().current_scene
	if scene_root:
		bt_player.call("set_scene_root_hint", scene_root)
	
	# Now add to scene tree (this triggers _enter_tree() initialization with tree and agent set)
	add_child(bt_player)
	
	# DEBUG: Check what owner was set
	print("[BotManager] BTPlayer added. owner=", bt_player.owner, " get_tree()=", bt_player.get_tree(), " scene_root=", bt_player.get_tree().current_scene if bt_player.get_tree() else "null")
	
	# Get the blackboard that BTPlayer created from the blackboard_plan and populate it
	var blackboard = bt_player.get_blackboard()
	if not blackboard:
		push_error("[BotManager] BTPlayer did not create a blackboard!")
		return
	
	# Populate the BTPlayer's blackboard with all required references
	blackboard.set_var("player", player)
	blackboard.set_var("game_instance", game_instance)
	blackboard.set_var("ai_manager", game_instance.ai_manager)
	blackboard.set_var("grid_sampler", grid_sampler)
	blackboard.set_var("hazard_predictor", hazard_predictor)
	blackboard.set_var("opponent_tracker", opponent_tracker)
	blackboard.set_var("bomb_planner", bomb_planner)
	blackboard.set_var("bomb_safety_checker", bomb_safety_checker)
	blackboard.set_var("personality", personality)
	
	# Initialize dynamic values
	blackboard.set_var("current_tile", player.get_tile_position())
	blackboard.set_var("time", Time.get_ticks_msec() / 1000.0)
	blackboard.set_var("target_cell", null)
	blackboard.set_var("in_danger", false)
	
	print("[BotManager] Blackboard populated for ", player.player_name)
	print("[BotManager] BehaviorTree set: ", bot_behavior_tree, " root_task: ", bot_behavior_tree.get("root_task") if bot_behavior_tree else "null")
	
	_bot_players[peer_id] = bt_player
	
	# IMPORTANT: Set active BEFORE setting update mode
	bt_player.set("active", true)
	bt_player.set("update_mode", 0) # 0 = MANUAL (we call update() ourselves in _physics_process)
	
	# Ensure BTPlayer process mode is set correctly
	bt_player.process_mode = Node.PROCESS_MODE_INHERIT
	
	# TESTING: Try explicitly calling restart() to initialize the behavior tree
	bt_player.call("restart")
	
	print("[BotManager] Bot %s BTPlayer setup complete: active=", bt_player.get("active"), " update_mode=", bt_player.get("update_mode"), " process_mode=", bt_player.process_mode)
	
	# Clean up when player is removed
	player.tree_exited.connect(func():
		_despawn_bot(peer_id)
	, Object.CONNECT_ONE_SHOT)

func _despawn_bot(peer_id: int) -> void:
	if _bot_players.has(peer_id):
		var bt_player = _bot_players[peer_id]
		if is_instance_valid(bt_player):
			bt_player.active = false
			bt_player.queue_free()
		_bot_players.erase(peer_id)
		print("[BotManager] Despawned bot (peer %d)" % peer_id)

func get_bot_controller(peer_id: int):
	return _bot_players.get(peer_id)

func _exit_tree() -> void:
	for bt_player in _bot_players.values():
		if is_instance_valid(bt_player):
			bt_player.active = false
			bt_player.queue_free()
	_bot_players.clear()

func refresh_perception() -> void:
	"""Force immediate refresh of perception modules (e.g. after bomb placement)"""
	if hazard_predictor:
		hazard_predictor.refresh(Time.get_ticks_msec() / 1000.0)
