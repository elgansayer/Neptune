extends Node

## Publish a completed physics tick after all actors have updated.
var authority: Node

func _ready() -> void:
	process_physics_priority = 100

func _physics_process(_delta: float) -> void:
	if is_instance_valid(authority) and authority.is_physics_processing():
		authority._publish_due_state()
