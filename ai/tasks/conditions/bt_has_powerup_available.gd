@tool
extends BTCondition
class_name BTHasPowerupAvailable

## Checks if any powerup items exist on the map
## Different from BTHasPowerup which checks if player owns a powerup ability

@export var max_distance: float = -1.0  ## Maximum search range (-1 = unlimited)

func _generate_name() -> String:
	if max_distance > 0:
		return "HasPowerupAvailable (range: %.0f)" % max_distance
	return "HasPowerupAvailable"

func _tick(_delta: float) -> int:
	var game_instance = blackboard.get_var("game_instance")
	var player = blackboard.get_var("player")
	var grid_sampler = blackboard.get_var("grid_sampler")
	
	if not game_instance or not player:
		return FAILURE
	
	# Check if any powerups exist in the game world
	if game_instance.powerups.size() == 0:
		blackboard.set_var("nearest_powerup", null)
		blackboard.set_var("nearest_powerup_tile", null)
		return FAILURE
	
	# If distance check is enabled, find nearest powerup within range
	if max_distance > 0 and grid_sampler:
		var player_tile = player.get_tile_position()
		var closest_powerup = null
		var closest_distance = INF
		
		for powerup in game_instance.powerups.values():
			if not is_instance_valid(powerup):
				continue
			
			var powerup_tile = grid_sampler.world_to_tile(powerup.position)
			var distance = grid_sampler.get_manhattan_distance(player_tile, powerup_tile)
			
			if distance < closest_distance:
				closest_distance = distance
				closest_powerup = powerup
		
		if closest_distance > max_distance:
			blackboard.set_var("nearest_powerup", null)
			blackboard.set_var("nearest_powerup_tile", null)
			return FAILURE
		
		# Store for subsequent nodes
		if closest_powerup:
			blackboard.set_var("nearest_powerup", closest_powerup)
			blackboard.set_var("nearest_powerup_tile", grid_sampler.world_to_tile(closest_powerup.position))
	
	return SUCCESS
