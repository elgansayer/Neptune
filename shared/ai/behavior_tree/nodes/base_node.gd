extends Resource
class_name BTNode

## Base class for behavior tree nodes. Returns true when action succeeds.

func tick(_blackboard: Dictionary, _delta: float) -> bool:
	return true
