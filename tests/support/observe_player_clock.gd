extends Node

func _ready() -> void:
	process_physics_priority = 50

func _physics_process(_delta: float) -> void:
	var player = get_parent()
	player.set_meta("clock_observation", {"time": player.game_instance.current_time_msec,
		"position": player.position})
