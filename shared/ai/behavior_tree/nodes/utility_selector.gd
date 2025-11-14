extends BTNode
class_name BTUtilitySelector

## Chooses child with highest score using optional scorer callable on the blackboard.

var children: Array = []
var score_func: Callable

func tick(blackboard: Dictionary, delta: float) -> bool:
	if children.is_empty():
		return false
	var best_child
	var best_score := -INF
	for child in children:
		var child_score := _score_child(child, blackboard)
		if child_score > best_score:
			best_score = child_score
			best_child = child
	if best_child == null:
		return false
	return best_child.tick(blackboard, delta)

func _score_child(child, blackboard: Dictionary) -> float:
	if score_func.is_valid():
		return score_func.call(child, blackboard)
	return 0.0
