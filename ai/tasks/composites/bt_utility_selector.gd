@tool
extends BTComposite
class_name BTUtilitySelector

## Limbo AI utility-based selector that scores children dynamically
## Picks the highest-scoring child based on game state evaluation

## Callable signature: func(child: BTTask, blackboard: Blackboard) -> float
## Should return a score where higher = better
@export var utility_function: Callable

func _generate_name() -> String:
	return "UtilitySelector"

func _tick(delta: float) -> int:
	if get_child_count() == 0:
		return FAILURE
	
	# If no utility function assigned, fall back to priority-based selection
	if not utility_function or not utility_function.is_valid():
		# Behave like standard BTSelector (try children in order)
		for i in get_child_count():
			var child = get_child(i)
			var child_status = child.execute(delta)
			if child_status != FAILURE:
				return child_status
		return FAILURE
	
	# Score all children
	var best_child = null
	var best_score = -INF
	
	for i in get_child_count():
		var child = get_child(i)
		var score = utility_function.call(child, blackboard)
		
		if score > best_score:
			best_score = score
			best_child = child
	
	# Execute highest-scoring child
	if best_child:
		var child_status = best_child.execute(delta)
		return child_status
	
	return FAILURE
