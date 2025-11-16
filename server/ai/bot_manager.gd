extends Node
class_name ServerBotManager

const _BOT_CONTROLLER_PATHS := [
	"res://ai/bot_controller_limbo.gd",  # LimboAI version (preferred)
	"res://ai/bot_controller.gd"  # Fallback to custom BT
]
var ServerBotControllerScript = _load_script_variant(_BOT_CONTROLLER_PATHS)

const GridSamplerScript = preload("res://shared/ai/perception/grid_sampler.gd")
const HazardPredictorScript = preload("res://shared/ai/perception/hazard_predictor.gd")
const OpponentTrackerScript = preload("res://shared/ai/perception/opponent_tracker.gd")
const BombPlannerScript = preload("res://shared/ai/perception/bomb_planner.gd")
const BombSafetyCheckerScript = preload("res://shared/ai/planning/bomb_safety_checker.gd")

var game_instance
var controllers: Array = []
var grid_sampler
var hazard_predictor
var opponent_tracker
var bomb_planner
var bomb_safety_checker  # New: time-aware BFS suicide check
var next_bot_peer_id := -1
var auto_spawned := false

const DEFAULT_PERSONALITY := "BALANCED"
const DEFAULT_BOT_COUNT := 3  # Adjust for heavier load testing as needed

func configure(instance) -> void:
	game_instance = instance
	grid_sampler = GridSamplerScript.new()
	grid_sampler.configure(game_instance, null, GameConfig.TILE_SIZE)
	hazard_predictor = HazardPredictorScript.new()
	hazard_predictor.configure(game_instance, grid_sampler)
	opponent_tracker = OpponentTrackerScript.new()
	bomb_planner = BombPlannerScript.new()
	bomb_planner.configure(grid_sampler, hazard_predictor)
	
	# Initialize new time-aware suicide checker
	bomb_safety_checker = BombSafetyCheckerScript.new()
	
	# Wait for ai_manager to be initialized in game_instance
	call_deferred("_configure_safety_checker")
	
	if DEFAULT_BOT_COUNT > 0:
		print("[BotManager] Queuing auto-spawn for %d bots" % DEFAULT_BOT_COUNT)
		call_deferred("_auto_spawn_bots")

func _configure_safety_checker() -> void:
	if game_instance != null and game_instance.ai_manager != null:
		bomb_safety_checker.configure(game_instance.ai_manager, grid_sampler)
		print("[BotManager] BombSafetyChecker configured with AIManager")

func _auto_spawn_bots() -> void:
	if auto_spawned:
		return
	auto_spawned = true
	print("[BotManager] Auto-spawning %d bots" % DEFAULT_BOT_COUNT)
	spawn_bots(DEFAULT_BOT_COUNT, DEFAULT_PERSONALITY)

func _physics_process(_delta: float) -> void:
	if game_instance == null:
		return
	hazard_predictor.refresh(Time.get_ticks_msec() / 1000.0)
	opponent_tracker.update_from_players(game_instance.players.values())
	
	# Update opponent intelligence profiles
	if game_instance.ai_manager != null:
		var bot_positions := {}
		for controller in controllers:
			if is_instance_valid(controller) and is_instance_valid(controller.player_ref):
				var bot_id = controller.player_ref.peer_id
				var bot_pos = controller.player_ref.get_tile_position()
				bot_positions[bot_id] = bot_pos
		
		game_instance.ai_manager.update_opponent_intel(bot_positions, game_instance.players, _delta)

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
	# Enable bot controller and behavior tree
	if ServerBotControllerScript == null:
		push_warning("[BotManager] Bot controller script unavailable; bot will be inactive")
		return
	var controller = ServerBotControllerScript.new()
	controller.configure(game_instance, player, personality, grid_sampler, hazard_predictor, opponent_tracker, bomb_planner, bomb_safety_checker)
	controllers.append(controller)
	add_child(controller)
	player.tree_exited.connect(func():
		controllers.erase(controller)
		if is_instance_valid(controller):
			controller.queue_free()
	, Object.CONNECT_ONE_SHOT)

static func _load_script_variant(paths: Array) -> Script:
	for path in paths:
		if ResourceLoader.exists(path):
			var script = load(path)
			# Check if script loaded successfully
			if script != null and script is Script:
				return script
	return null
