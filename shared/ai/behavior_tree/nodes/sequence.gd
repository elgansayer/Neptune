extends "res://shared/ai/behavior_tree/nodes/base_node.gd"
class_name LegacyBTSequence

var children: Array = []

func tick(blackboard: Dictionary, delta: float) -> bool:
	for child in children:
		if not child.tick(blackboard, delta):
			return false
	return true
