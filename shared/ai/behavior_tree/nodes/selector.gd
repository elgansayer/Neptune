extends "res://shared/ai/behavior_tree/nodes/base_node.gd"
class_name BTSelector

var children: Array = []

func tick(blackboard: Dictionary, delta: float) -> bool:
	for child in children:
		if child.tick(blackboard, delta):
			return true
	return false
