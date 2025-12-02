extends "res://items/item.gd"

## Speed increase power-up (roller skates)

func award_player(player):
	if player.has_method("add_speed"):
		player.add_speed(1)
	elif "stat_skates" in player:
		player.stat_skates = player.stat_skates + 1
