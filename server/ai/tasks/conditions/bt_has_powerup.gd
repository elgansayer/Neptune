@tool
extends BTCondition
class_name BTHasPowerup

## Checks if the player has a specific powerup ability

enum PowerupType {
	BOMB_KICKER,   ## Can kick bombs
	POWER_GLOVE,   ## Can pick up and throw bombs
	SPEED_BOOST,   ## Has speed increase
	BOMB_INCREASE, ## Has max bombs increased
	RANGE_INCREASE ## Has bomb range increased
}

@export var powerup_type: PowerupType = PowerupType.BOMB_KICKER

func _generate_name() -> String:
	var type_names = {
		PowerupType.BOMB_KICKER: "BombKicker",
		PowerupType.POWER_GLOVE: "PowerGlove",
		PowerupType.SPEED_BOOST: "SpeedBoost",
		PowerupType.BOMB_INCREASE: "BombIncrease",
		PowerupType.RANGE_INCREASE: "RangeIncrease"
	}
	return "HasPowerup(%s)" % type_names.get(powerup_type, "Unknown")

func _tick(delta: float) -> int:
	var player = blackboard.get_var("player")
	
	if not player:
		push_warning("[BTHasPowerup] Missing player in blackboard")
		return FAILURE
	
	match powerup_type:
		PowerupType.BOMB_KICKER:
			return SUCCESS if player.has_bomb_kicker else FAILURE
		PowerupType.POWER_GLOVE:
			return SUCCESS if player.has_power_glove else FAILURE
		PowerupType.SPEED_BOOST:
			return SUCCESS if player.speed_multiplier > 1.0 else FAILURE
		PowerupType.BOMB_INCREASE:
			return SUCCESS if player.max_bombs > 1 else FAILURE
		PowerupType.RANGE_INCREASE:
			return SUCCESS if player.bomb_range > 2 else FAILURE
		_:
			push_warning("[BTHasPowerup] Unknown powerup type: %s" % powerup_type)
			return FAILURE
