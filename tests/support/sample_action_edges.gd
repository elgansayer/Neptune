extends Node

signal captured
var packet: Dictionary = {}

func _physics_process(_delta: float) -> void:
	packet = {"action_pressed": Input.is_action_just_pressed("player_action"), "action_released": Input.is_action_just_released("player_action")}
	set_physics_process(false)
	captured.emit()
