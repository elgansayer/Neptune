extends Node

# Utility to advance physics frames deterministically.
# Use await tick_util.step_frames(n) inside tests.

func step_frames(count: int) -> void:
	for i in range(count):
		await get_tree().physics_frame
