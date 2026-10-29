extends ServerBotManager

## Observation only: production update behaviour is always invoked unchanged.
var observed_physics_calls := 0

func _physics_process(delta: float) -> void:
	observed_physics_calls += 1
	super(delta)
