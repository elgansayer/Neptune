extends "res://tests/support/fixture_game_instance.gd"

var command_trace: Array[Dictionary] = []
var reject_once_action := ""

func submit_player_command(peer_id: int, command: Variant) -> Dictionary:
	var action := str(command.get("action", "")) if command is Dictionary else ""
	var result: Dictionary
	if action == reject_once_action and not action.is_empty():
		reject_once_action = ""
		result = {"accepted": false, "reason": "fixture_refusal", "action": action, "bomb_ids": []}
	else:
		result = super(peer_id, command)
	var actor = players.get(peer_id)
	command_trace.append({"peer_id": peer_id, "action": action, "accepted": result.accepted,
		"reason": result.reason, "tick": simulation_tick,
		"position": actor.position if is_instance_valid(actor) else Vector2.ZERO,
		"facing": actor.last_move_direction if is_instance_valid(actor) else Vector2.ZERO})
	return result
