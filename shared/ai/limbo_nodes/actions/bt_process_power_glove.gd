@tool
extends BTAction
class_name BTProcessPowerGlove

## Handles Power Glove logic for player-controlled entities
## Priority: Throw (if carrying) -> Pickup (if bomb underfoot) -> Place (if can place)
## This node implements the complex Power Glove interaction logic

@export var consume_input_on_action: bool = true  ## Consume input after processing action

func _generate_name() -> String:
	return "ProcessPowerGlove"

func _tick(delta: float) -> int:
	var player = blackboard.get_var("player")
	var game_instance = blackboard.get_var("game_instance")
	var action_pressed = blackboard.get_var("action_pressed", false)
	
	if not player or not game_instance:
		push_warning("[BTProcessPowerGlove] Missing player or game_instance in blackboard")
		return FAILURE
	
	# Only process if action button was pressed
	if not action_pressed:
		return SUCCESS  # No action this frame
	
	# PRIORITY 1: Throw if currently carrying a bomb
	if player.is_carrying_bomb():
		player.throw_carried_bomb()
		_consume_input_if_enabled()
		blackboard.set_var("last_action", "throw_bomb")
		return SUCCESS
	
	# PRIORITY 2: Try to pick up bomb at current position
	if _try_pickup_bomb(player, game_instance):
		_consume_input_if_enabled()
		blackboard.set_var("last_action", "pickup_bomb")
		return SUCCESS
	
	# PRIORITY 3: Place new bomb if allowed and no bomb at position
	var player_tile = player.get_tile_position()
	if player.can_place_bomb() and not _bomb_at_position(player_tile, game_instance):
		game_instance.place_bomb(player)
		_consume_input_if_enabled()
		blackboard.set_var("last_action", "place_bomb")
		return SUCCESS
	
	# Action pressed but nothing happened (probably at max bombs or bomb already there)
	blackboard.set_var("last_action", "none")
	return SUCCESS

func _try_pickup_bomb(player, game_instance) -> bool:
	"""Try to pick up a bomb at the player's current tile"""
	var player_tile = player.get_tile_position()
	
	# Find bomb at player's position
	for bomb_id in game_instance.bombs:
		var bomb = game_instance.bombs[bomb_id]
		if not is_instance_valid(bomb):
			continue
		
		var bomb_tile = bomb.get_tile_position()
		if bomb_tile == player_tile:
			# Attempt pickup
			if player.try_pickup_bomb(bomb):
				print("[BTProcessPowerGlove] Player picked up bomb at ", player_tile)
				return true
	
	return false

func _bomb_at_position(tile: Vector2i, game_instance) -> bool:
	"""Check if there's a bomb at the given tile"""
	for bomb_id in game_instance.bombs:
		var bomb = game_instance.bombs[bomb_id]
		if is_instance_valid(bomb) and bomb.get_tile_position() == tile:
			return true
	return false

func _consume_input_if_enabled():
	"""Consume input from buffer if enabled"""
	if not consume_input_on_action:
		return
	
	var input_buffer = blackboard.get_var("input_buffer")
	if input_buffer:
		input_buffer.consume_latest()
		# Clear the action_pressed flag
		blackboard.set_var("action_pressed", false)
