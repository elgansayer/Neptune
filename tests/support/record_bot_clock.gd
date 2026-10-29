@tool
extends BTAction

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var game = blackboard.get_var("game_instance")
	var record := {"tick": game.get("simulation_tick"),
		"game_ms": game.current_time_msec, "board_sec": blackboard.get_var("time")}
	if not game.bombs.is_empty():
		var bomb = game.bombs.values()[0]
		record["bomb_elapsed"] = bomb.explosion_timer
		record["bomb_deadline"] = game.ai_manager.threat_matrix.get("4,4", INF)
	player.get_meta("clock_records").append(record)
	return SUCCESS
