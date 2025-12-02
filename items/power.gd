extends "res://items/item.gd"

## Fire/Range increase power-up

func award_player(player):
	if player.has_method("add_range"):
		player.add_range(1)
	elif "stat_power" in player:
		player.stat_power = player.stat_power + 1
