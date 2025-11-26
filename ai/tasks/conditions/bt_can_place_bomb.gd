@tool
extends BTCondition
class_name BTCanPlaceBomb

## Checks if the player has bomb capacity available (can place a bomb)
## Returns SUCCESS if player can place a bomb, FAILURE otherwise

func _generate_name() -> String:
	return "CanPlaceBomb?"

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	
	if not player:
		return FAILURE
	
	# Check if player is dead
	if player.is_dead:
		return FAILURE
	
	# Check if player can place a bomb (has capacity)
	if player.can_place_bomb():
		return SUCCESS
	
	# At max bomb capacity - cannot place more bombs
	return FAILURE
