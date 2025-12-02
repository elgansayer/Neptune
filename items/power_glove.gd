extends "res://items/item.gd"

## Power Glove - allows picking up and throwing bombs

func award_player(player):
	if player.has_method("enable_power_glove"):
		player.enable_power_glove()
	elif "stat_power_glove" in player:
		player.stat_power_glove = true
