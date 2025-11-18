@tool
extends BTAction
class_name BTFindPowerup

## Finds nearest powerup and calculates path toward it
## Stores target tile for subsequent movement nodes

@export var target_tile_var: StringName = &"target_cell"  ## Blackboard variable to store target tile
@export var prioritize_type: String = ""  ## Preferred powerup type (empty = any)

func _generate_name() -> String:
	if prioritize_type:
		return "FindPowerup(%s) → %s" % [prioritize_type, target_tile_var]
	return "FindPowerup → %s" % target_tile_var

func _tick(_delta: float) -> int:
	var game_instance = blackboard.get_var("game_instance")
	var player = blackboard.get_var("player")
	var grid_sampler = blackboard.get_var("grid_sampler")
	
	if not game_instance or not player or not grid_sampler:
		return FAILURE
	
	if game_instance.powerups.size() == 0:
		return FAILURE
	
	var player_tile = player.get_tile_position()
	var closest_powerup = null
	var closest_distance = INF
	var closest_tile: Vector2i
	
	# Find nearest powerup (with optional type priority)
	for powerup in game_instance.powerups:
		if not is_instance_valid(powerup):
			continue
		
		var powerup_tile = grid_sampler.world_to_tile(powerup.position)
		var distance = grid_sampler.get_manhattan_distance(player_tile, powerup_tile)
		
		# Priority boost for preferred type
		var priority_bonus = 0.0
		if prioritize_type and powerup.has("powerup_type"):
			if powerup.powerup_type == prioritize_type:
				priority_bonus = -5.0  # Reduce effective distance for preferred types
		
		var effective_distance = distance + priority_bonus
		
		if effective_distance < closest_distance:
			closest_distance = effective_distance
			closest_powerup = powerup
			closest_tile = powerup_tile
	
	if closest_powerup == null:
		return FAILURE
	
	# Calculate intermediate target (move one step toward powerup)
	var direction = (closest_tile - player_tile)
	var target: Vector2i
	
	if abs(direction.x) > abs(direction.y):
		target = player_tile + Vector2i(sign(direction.x), 0)
	else:
		target = player_tile + Vector2i(0, sign(direction.y))
	
	# Validate target is walkable
	var ai_manager = blackboard.get_var("ai_manager")
	if ai_manager and not ai_manager.is_walkable(target):
		# Try alternate direction
		if abs(direction.x) > abs(direction.y):
			target = player_tile + Vector2i(0, sign(direction.y))
		else:
			target = player_tile + Vector2i(sign(direction.x), 0)
		
		# If still blocked, just stay put (will retry next tick)
		if not ai_manager.is_walkable(target):
			target = player_tile
	
	# Store in blackboard
	blackboard.set_var(target_tile_var, target)
	blackboard.set_var("powerup_target", closest_tile)
	blackboard.set_var("powerup_type", closest_powerup.powerup_type if closest_powerup.has("powerup_type") else "unknown")
	
	return SUCCESS
