@tool
extends BTAction

## Delay a new intentional goal while keeping the native tree and movement
## clock at physics cadence. The higher-priority public-hazard reflex bypasses
## this wait; this is a strategic reaction delay, not delayed observation data.
const SimulationTime = preload("res://shared/ai/simulation_time.gd")

var _ready_at_msec := 0.0

func _enter() -> void:
	var now := SimulationTime.milliseconds(blackboard)
	var reaction := maxf(0.0, float(blackboard.get_var("reaction_time_ms", 0.0)))
	_ready_at_msec = now + reaction
	blackboard.set_var("strategic_ready_at_msec", _ready_at_msec)

func _tick(_delta: float) -> int:
	if SimulationTime.milliseconds(blackboard) < _ready_at_msec:
		var player = blackboard.get_var("player", null)
		if is_instance_valid(player): player.set_input(0, 0)
		return RUNNING
	blackboard.set_var("last_strategic_decision_msec", SimulationTime.milliseconds(blackboard))
	return SUCCESS
