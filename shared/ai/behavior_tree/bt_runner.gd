extends Resource
class_name BehaviorTreeRunner

## Lightweight behavior tree runner that ticks a root node with a shared blackboard.

var root_node
var blackboard := {}

func set_root(node) -> void:
	root_node = node

func set_blackboard(new_blackboard: Dictionary) -> void:
	blackboard = new_blackboard

func tick(delta: float) -> void:
	if root_node == null:
		return
	root_node.tick(blackboard, delta)
