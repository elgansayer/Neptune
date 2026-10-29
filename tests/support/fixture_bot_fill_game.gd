extends "res://tests/support/fixture_game_instance.gd"

## Inject a structured provisioning refusal after real successful spawns.
var refuse_after := -1
var provision_calls := 0

func spawn_bot(personality: String = "BALANCED", spawn_position: Vector2 = Vector2.ZERO) -> Dictionary:
	if refuse_after >= 0 and provision_calls >= refuse_after:
		return {"accepted": false, "reason": "injected_provision_refusal"}
	provision_calls += 1
	return super(personality, spawn_position)
