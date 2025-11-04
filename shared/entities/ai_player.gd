extends "res://shared/entities/server_player.gd"
# AIPlayer - AI-Controlled Player
# Note: Using full resource path instead of class_name to fix parse issues
# Extends ServerPlayer but generates input locally instead of from network

const AIBotController = preload("res://shared/ai/ai_bot_controller.gd")
const AIPersonality = preload("res://shared/ai/ai_personalities.gd")

var controller: AIBotController
var personality_type: int  # AIPersonality.Type enum value
var bot_name: String = "Bot"

func is_ai_bot() -> bool:
	"""Helper to identify AI players"""
	return true

func setup_ai(game_instance: Node2D, personality: int = 0):  # 0 = BALANCED
	"""Initialize AI controller with personality"""
	personality_type = personality
	controller = AIBotController.new(game_instance, personality)
	
	# Generate bot name based on personality
	var personality_name = controller.get_personality_name()
	var bot_number = randi() % 1000
	bot_name = "%s_Bot_%03d" % [personality_name, bot_number]
	username = bot_name
	
	print("[AIPlayer] Initialized: ", bot_name, " (", personality_name, ")")

func _physics_process(delta):
	if not controller:
		super._physics_process(delta)
		return
	
	# Generate AI decision
	var input_data = controller.decide_action(self)
	
	# Apply AI-generated input
	set_input(input_data.direction.x, input_data.direction.y)
	
	# Store bomb request for game_instance to process
	if input_data.place_bomb and can_place_bomb():
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
