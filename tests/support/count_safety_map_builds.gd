extends "res://shared/ai/perception/hazard_predictor.gd"

var safety_map_builds := 0

func _build_safety_map() -> void:
	safety_map_builds += 1
	super()
