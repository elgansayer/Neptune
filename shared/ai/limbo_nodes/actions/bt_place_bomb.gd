@tool
extends BTAction
class_name BTPlaceBomb

## Places a bomb at the player's current position
## Checks if player can place a bomb before attempting

@export var check_capacity: bool = true  ## Verify player hasn't exceeded max bombs
@export var check_existing: bool = true  ## Verify no bomb already at position

func _generate_name() -> String:
	return "PlaceBomb"

func _tick(delta: float) -> int:
	var player = blackboard.get_var("player")
	var game_instance = blackboard.get_var("game_instance")
	
	if not player:
		push_warning("[BTPlaceBomb] Missing player in blackboard")
		return FAILURE
	
	if not game_instance:
		push_warning("[BTPlaceBomb] Missing game_instance in blackboard")
		return FAILURE
	
	# Check if player can place a bomb
	if check_capacity and not player.can_place_bomb():
		# Can't place bomb (at max capacity or cooldown)
		return FAILURE
	
	# Check if there's already a bomb at this position
	if check_existing:
		var player_tile = player.get_tile_position()
		if _bomb_at_position(player_tile, game_instance):
			# Already a bomb here
			return FAILURE
	
	# Place the bomb
	game_instance.place_bomb(player)
	
	# Store bomb placement info in blackboard for debugging/tracking
	blackboard.set_var("last_bomb_placed_at", player.get_tile_position())
	blackboard.set_var("last_bomb_placed_time", Time.get_ticks_msec() / 1000.0)
	
	return SUCCESS

func _bomb_at_position(tile: Vector2i, game_instance) -> bool:
	"""Check if there's already a bomb at the given tile"""
	for bomb_id in game_instance.bombs:
		var bomb = game_instance.bombs[bomb_id]
		if is_instance_valid(bomb) and bomb.get_tile_position() == tile:
			return true
	return false
