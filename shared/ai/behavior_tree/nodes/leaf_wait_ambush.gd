extends BTNode
class_name BTWaitAmbushNode

## Keeps the bot idle for a short window, useful for trapper personalities.

var wait_time := 1.0
var elapsed := 0.0

func tick(_blackboard: Dictionary, delta: float) -> bool:
	var profile: Dictionary = _blackboard.get("personality", {})
	if profile.has("ambush_window"):
		wait_time = profile["ambush_window"]
	elapsed += delta
	_blackboard["move_vector"] = Vector2.ZERO
	if elapsed >= wait_time:
		elapsed = 0.0
	return true
