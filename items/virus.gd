extends "res://items/item.gd"

## Virus/Skull power-up - causes negative effects

func award_player(player):
	if player.has_method("got_virus"):
		player.got_virus()
	elif player.has_method("apply_virus"):
		player.apply_virus()
