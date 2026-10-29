extends "res://tests/support/fixture_game_instance.gd"

var clock_publications: Array[Dictionary] = []

func sync_state_to_clients():
	super()
	for player in players.values():
		if player.has_meta("clock_observation"):
			clock_publications.append({"time": current_time_msec, "position": player.position,
				"observed": player.get_meta("clock_observation").duplicate()})
