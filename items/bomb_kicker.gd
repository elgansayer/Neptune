extends "res://items/item.gd"

## Bomb Kicker - allows kicking bombs

func award_player(player):
	if player.has_method("enable_bomb_kicker"):
		player.enable_bomb_kicker()
	elif "stat_bomb_kicker" in player:
		player.stat_bomb_kicker = true
