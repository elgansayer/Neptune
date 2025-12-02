@tool
extends BTAction
class_name BTFindPowerup

## Finds nearest VALUABLE powerup and calculates path toward it
## Uses smart scoring to prioritize good items and AVOID negative items (GETA, SKULL)
## Stores target tile for subsequent movement nodes

const ServerPowerUpScript = preload("res://shared/entities/server_powerup.gd")

@export var target_tile_var: StringName = &"target_cell"  ## Blackboard variable to store target tile
@export var prioritize_type: String = ""  ## Preferred powerup type (empty = any)
@export var min_value_threshold: float = 0.0  ## Minimum value to consider (filters negative items)

func _generate_name() -> String:
	if prioritize_type:
		return "FindPowerup(%s) → %s" % [prioritize_type, target_tile_var]
	return "FindPowerup → %s" % target_tile_var

## Calculate how valuable a powerup is for this specific player
## Returns negative values for items that should be AVOIDED
static func get_powerup_value(powerup_type: int, player) -> float:
	match powerup_type:
		# === EXTREMELY VALUABLE - Always grab! ===
		ServerPowerUpScript.PowerUpType.FULL_FIRE:
			if player.bomb_range < 16:
				return 150.0  # Max fire is game-changing
			return 5.0  # Already have max
		
		# === ABILITY ITEMS - Very valuable if don't have ===
		ServerPowerUpScript.PowerUpType.BOMB_KICKER:
			return 100.0 if not player.has_bomb_kicker else 5.0
		ServerPowerUpScript.PowerUpType.POWER_GLOVE:
			return 100.0 if not player.has_power_glove else 5.0
		ServerPowerUpScript.PowerUpType.LINE_BOMB:
			return 80.0 if not player.has_line_bomb else 5.0
		
		# === STAT ITEMS - Diminishing returns ===
		ServerPowerUpScript.PowerUpType.BOMB_INCREASE:
			# More valuable if we have few bombs
			if player.max_bombs < 3:
				return 70.0
			elif player.max_bombs < 6:
				return 40.0
			else:
				return 15.0  # Already have plenty
		
		ServerPowerUpScript.PowerUpType.RANGE_INCREASE:
			# Fire range is very important early game
			if player.bomb_range < 3:
				return 80.0
			elif player.bomb_range < 5:
				return 50.0
			else:
				return 20.0
		
		ServerPowerUpScript.PowerUpType.SPEED_INCREASE:
			# Speed helps escape but diminishing returns
			if player.skate_count < 2:
				return 50.0
			elif player.skate_count < 5:
				return 30.0
			else:
				return 10.0
		
		# === SPECIAL BOMB TYPES - Medium value ===
		ServerPowerUpScript.PowerUpType.REMOTE_BOMB:
			return 60.0 if player.bomb_type != 1 else 5.0  # 1 = remote
		ServerPowerUpScript.PowerUpType.POWER_BOMB, ServerPowerUpScript.PowerUpType.PIERCE_BOMB:
			return 50.0 if player.bomb_type != 2 else 5.0  # 2 = power
		ServerPowerUpScript.PowerUpType.RUBBER_BOMB:
			return 40.0 if player.bomb_type != 3 else 5.0  # 3 = rubber
		
		# === HEART - Extra life is valuable! ===
		ServerPowerUpScript.PowerUpType.HEART:
			return 90.0
		
		# === NEGATIVE ITEMS - AVOID! ===
		ServerPowerUpScript.PowerUpType.GETA:
			return -100.0  # Slows us down!
		ServerPowerUpScript.PowerUpType.SKULL, ServerPowerUpScript.PowerUpType.VIRUS:
			return -150.0  # Random curse - very bad!
		
		_:
			return 10.0  # Unknown = low priority

func _tick(_delta: float) -> int:
	var game_instance = blackboard.get_var("game_instance")
	var player = blackboard.get_var("player")
	var grid_sampler = blackboard.get_var("grid_sampler")
	
	if not game_instance or not player or not grid_sampler:
		return FAILURE
	
	if game_instance.powerups.size() == 0:
		return FAILURE
	
	var player_tile = player.get_tile_position()
	var best_powerup = null
	var best_score = -INF
	var best_tile: Vector2i
	
	# Find best powerup using value/distance scoring
	for powerup_id in game_instance.powerups:
		var powerup = game_instance.powerups[powerup_id]
		if not is_instance_valid(powerup):
			continue
		
		var powerup_type = powerup.powerup_type if "powerup_type" in powerup else 0
		var value = get_powerup_value(powerup_type, player)
		
		# Skip negative value items entirely!
		if value < min_value_threshold:
			continue
		
		var powerup_tile = grid_sampler.world_to_tile(powerup.position)
		var distance = grid_sampler.get_manhattan_distance(player_tile, powerup_tile)
		
		# Score = value - distance penalty (closer is better)
		# Distance penalty is 5 points per tile
		var score = value - (distance * 5.0)
		
		# Priority boost for preferred type
		if prioritize_type and str(powerup_type) == prioritize_type:
			score += 20.0
		
		if score > best_score:
			best_score = score
			best_powerup = powerup
			best_tile = powerup_tile
	
	if best_powerup == null:
		return FAILURE
	
	# Calculate intermediate target (move one step toward powerup)
	var direction = (best_tile - player_tile)
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
	blackboard.set_var("powerup_target", best_tile)
	blackboard.set_var("powerup_type", best_powerup.powerup_type if "powerup_type" in best_powerup else 0)
	blackboard.set_var("powerup_value", best_score)
	
	return SUCCESS
