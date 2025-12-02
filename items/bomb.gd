extends "res://items/item.gd"

## Bomb increase power-up

func award_player(player):
	if player.has_method("add_bomb"):
		player.add_bomb(1)
	elif "stat_bombs" in player:
		player.stat_bombs = player.stat_bombs + 1
