@tool
extends BTAction

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	player.set_meta("fixture_bt_ticks", int(player.get_meta("fixture_bt_ticks", 0)) + 1)
	return RUNNING
