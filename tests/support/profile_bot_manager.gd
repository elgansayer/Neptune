extends ServerBotManager

## Observation-only instrumentation. The production manager owns every decision.
var update_cost_usec: Array[int] = []

func _init() -> void:
	super()
	profile_updates = true

func _physics_process(delta: float) -> void:
	var active: bool = game_instance != null and game_instance.match_active
	var started := Time.get_ticks_usec()
	super(delta)
	if active and update_cost_usec.size() < 4096:
		update_cost_usec.append(Time.get_ticks_usec() - started)
