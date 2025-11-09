extends "res://shared/entities/server_player.gd"
# AIPlayer - AI-Controlled Player
# Note: Using full resource path instead of class_name to fix parse issues
# Extends ServerPlayer but generates input locally instead of from network

const AIBotController = preload("res://shared/ai/ai_bot_controller.gd")
const ImprovedAIController = preload("res://shared/ai/improved_ai_controller.gd")
const AIPersonality = preload("res://shared/ai/ai_personalities.gd")

var controller  # Can be AIBotController or ImprovedAIController
var personality_type: int  # AIPersonality.Type enum value
var bot_name: String = "Bot"
var use_improved_ai: bool = true  # Set to true to use new intelligent AI

func is_ai_bot() -> bool:
	"""Helper to identify AI players"""
	return true

func setup_ai(game_instance: Node2D, personality: int = 0):  # 0 = BALANCED
	"""Initialize AI controller with personality"""
	personality_type = personality
	
	# Choose AI controller type
	if use_improved_ai:
		controller = ImprovedAIController.new(game_instance, personality)
		print("[AIPlayer] Using IMPROVED AI system")
	else:
		controller = AIBotController.new(game_instance, personality)
		print("[AIPlayer] Using legacy AI system")
	
	# Generate bot name based on personality
	var personality_name = controller.get_personality_name()
	var bot_number = randi() % 1000
	bot_name = "%s_Bot_%03d" % [personality_name, bot_number]
	username = bot_name
	
	print("[AIPlayer] Initialized: ", bot_name, " (", personality_name, ")")
	
	# Setup debug visualizer if in debug mode (deferred until in scene tree)
	if OS.is_debug_build() and use_improved_ai:
		# Defer setup until we're in the scene tree
		call_deferred("_setup_debug_visualizer_deferred", game_instance)

func _setup_debug_visualizer_deferred(game_ref: Node2D):
	"""Deferred debug visualizer setup after AI is in scene tree"""
	if is_instance_valid(controller) and controller.has_method("setup_debug_visualizer"):
		controller.setup_debug_visualizer(game_ref, self)

func _physics_process(delta):
	if not controller:
		print("[AIPlayer] ERROR: No controller for ", bot_name)
		super._physics_process(delta)
		return

	if is_dead:
		# Ensure dead bots stay inactive
		super._physics_process(delta)
		return
	
	# Generate AI decision
	var input_data: Dictionary = controller.decide_action(self)
	
	# Debug: Log occasionally
	if Engine.get_physics_frames() % 120 == 0:  # Every 2 seconds at 60fps
		print("[AIPlayer] ", bot_name, " decision: ", input_data.get("reasoning", "no reasoning"))
	
	# Apply AI-generated input (use bracket access for Dictionary)
	var dir: Vector2 = input_data.get("direction", Vector2.ZERO)
	set_input(dir.x, dir.y)
	
	# Store bomb request for game_instance to process
	if input_data.get("place_bomb", false) and can_place_bomb():
		request_bomb_placement()
	
	# Call parent physics process to handle movement
	super._physics_process(delta)

func get_bot_info() -> Dictionary:
	"""Returns information about this bot for debugging"""
	return {
		"name": bot_name,
		"personality": controller.get_personality_name() if controller else "None",
		"position": position,
		"tile": get_tile_position(),
		"bombs_available": max_bombs - bombs_placed,
		"bomb_range": bomb_range
	}
