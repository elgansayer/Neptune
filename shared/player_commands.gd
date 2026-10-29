extends RefCounted

## Trusted server command boundary; no RPC, scripts or client positions accepted.
const PACKET_FIELDS := ["input_x", "input_y", "place_bomb", "action_pressed", "action_released"]
const SHAPES := {
	"move": ["action", "x", "y"], "place_bomb": ["action"],
	"pickup_bomb": ["action", "bomb_id"], "throw_bomb": ["action"],
	"mount_action": ["action"], "detonate_remote": ["action"],
	"action_press": ["action"], "action_release": ["action"],
}
var _game: Node

func _init(game: Node) -> void:
	_game = game

static func result(accepted: bool, reason: String, action: String = "", ids: Array = []) -> Dictionary:
	return {"accepted": accepted, "reason": reason, "action": action, "bomb_ids": ids}

static func valid_axis(value: Variant) -> bool:
	return typeof(value) in [TYPE_INT, TYPE_FLOAT] and is_finite(float(value)) and absf(float(value)) <= 1.0

static func validate_packet(packet: Dictionary) -> Dictionary:
	for key in packet:
		if not key is String or key not in PACKET_FIELDS:
			return result(false, "unknown_field", "packet")
	if not valid_axis(packet.get("input_x", 0.0)) or not valid_axis(packet.get("input_y", 0.0)):
		return result(false, "invalid_movement", "packet")
	for key in ["place_bomb", "action_pressed", "action_released"]:
		if not packet.get(key, false) is bool:
			return result(false, "invalid_action_flag", "packet")
	var normalised := {"input_x": float(packet.get("input_x", 0.0)), "input_y": float(packet.get("input_y", 0.0))}
	for key in ["place_bomb", "action_pressed", "action_released"]:
		normalised[key] = packet.get(key, false)
	var checked := result(true, "validated", "packet")
	checked["packet"] = normalised
	return checked

func _actor_reason(player, active: bool = true) -> String:
	if not is_instance_valid(player) or _game.players.get(player.peer_id) != player:
		return "unknown_player"
	if player.game_instance != _game:
		return "foreign_player"
	if active and not _game.match_active:
		return "match_inactive"
	if active and player.is_dead:
		return "dead_player"
	return ""

func submit(peer_id: int, command: Dictionary) -> Dictionary:
	var action = command.get("action", "")
	if not action is String or not SHAPES.has(action):
		return result(false, "unknown_action")
	for key in command:
		if key not in SHAPES[action]:
			return result(false, "unknown_field", action)
	if action == "move" and (not valid_axis(command.get("x", 0.0)) or not valid_axis(command.get("y", 0.0))):
		return result(false, "invalid_movement", action)
	var player = _game.players.get(peer_id)
	var neutral: bool = action == "move" and command.get("x", 0.0) == 0 and command.get("y", 0.0) == 0
	var reason := _actor_reason(player, not neutral and action != "action_release")
	if not reason.is_empty():
		return result(false, reason, action)
	match action:
		"move":
			player.input_direction = Vector2(float(command.get("x", 0.0)), float(command.get("y", 0.0)))
			return result(true, "moved", action)
		"action_release":
			player.action_button_pressed = false
			return result(true, "released", action)
		"place_bomb":
			var placed: Dictionary = _game.place_bomb(player)
			placed["action"] = action
			return placed
	# Geometry-dependent abilities must not cast invalid positions to grid IDs.
	if not player.position.is_finite():
		return result(false, "invalid_position", action)
	match action:
		"action_press":
			var performed: Dictionary
			if player.is_mounted:
				performed = submit(peer_id, {"action": "mount_action"})
			elif player.has_power_glove:
				if player.is_carrying_bomb():
					performed = submit(peer_id, {"action": "throw_bomb"})
				else:
					var bomb = _game.get_bomb_at_tile(player.get_tile_position())
					performed = submit(peer_id, {"action": "pickup_bomb", "bomb_id": bomb.bomb_id}) if is_instance_valid(bomb) else submit(peer_id, {"action": "place_bomb"})
			elif player.bomb_type == ServerBomb.BOMB_TYPE_REMOTE:
				performed = submit(peer_id, {"action": "detonate_remote"})
			else:
				return result(false, "ability_unavailable", action)
			if performed.accepted:
				player.action_button_pressed = true
			return performed
		"pickup_bomb":
			if not player.has_power_glove:
				return result(false, "ability_unavailable", action)
			if player.is_carrying_bomb():
				return result(false, "already_carrying", action)
			var bomb_id = command.get("bomb_id")
			if not bomb_id is String or bomb_id.is_empty() or bomb_id.length() > 64:
				return result(false, "invalid_bomb_id", action)
			var bomb = _game.bombs.get(bomb_id)
			if not is_instance_valid(bomb):
				return result(false, "unknown_bomb", action)
			if bomb.game_instance != _game:
				return result(false, "foreign_bomb", action)
			if player.get_tile_position() != bomb.get_tile_position():
				return result(false, "not_on_bomb", action)
			if not bomb.can_be_picked_up():
				return result(false, "bomb_unavailable", action)
			var picked: bool = player._apply_pickup_bomb(bomb)
			return result(picked, "picked_up" if picked else "pickup_failed", action, [bomb_id] if picked else [])
		"throw_bomb":
			if not player.has_power_glove:
				return result(false, "ability_unavailable", action)
			var bomb = player.carried_bomb
			if not is_instance_valid(bomb):
				return result(false, "not_carrying", action)
			if _game.bombs.get(bomb.bomb_id) != bomb or bomb.game_instance != _game:
				return result(false, "foreign_bomb", action)
			if bomb.carrying_player != player or bomb.bomb_state != ServerBomb.BombState.CARRIED:
				return result(false, "not_carrier", action)
			if not player.last_move_direction.is_finite():
				return result(false, "invalid_direction", action)
			var thrown: bool = player._apply_throw_bomb()
			return result(thrown, "thrown" if thrown else "throw_failed", action, [bomb.bomb_id] if thrown else [])
		"mount_action":
			if not player.is_mounted or not is_instance_valid(player.mounted_tirra) or player.mounted_tirra.get_parent() != player or not player.mounted_tirra.has_method("run_action"):
				return result(false, "ability_unavailable", action)
			if player.tirra_action_cooldown > 0.0:
				return result(false, "cooldown", action)
			if not player.last_move_direction.is_finite():
				return result(false, "invalid_direction", action)
			var started: bool = player._apply_tirra_action()
			return result(started, "mount_started" if started else "mount_unavailable", action)
		"detonate_remote":
			if player.bomb_type != ServerBomb.BOMB_TYPE_REMOTE:
				return result(false, "ability_unavailable", action)
			var bomb_id: String = _game._detonate_oldest_remote_bomb(player)
			return result(not bomb_id.is_empty(), "detonated" if not bomb_id.is_empty() else "no_remote_bomb", action, [bomb_id] if not bomb_id.is_empty() else [])
	return result(false, "unknown_action", action)

func apply_packet(peer_id: int, packet: Dictionary) -> Dictionary:
	var checked := validate_packet(packet)
	if not checked.accepted:
		return checked
	var data: Dictionary = checked.packet
	var movement: Dictionary = _game.submit_player_command(peer_id, {"action": "move", "x": data.input_x, "y": data.input_y})
	if not movement.accepted:
		return movement
	var actions: Array[Dictionary] = []
	if data.action_pressed:
		actions.append(_game.submit_player_command(peer_id, {"action": "action_press"}))
	if data.place_bomb:
		var player = _game.players[peer_id]
		# Space is also the glove's place/pickup/throw control. Coalesce both
		# button edges into one glove action; mounted Space remains placement.
		if player.has_power_glove and not player.is_mounted:
			if not data.action_pressed:
				actions.append(_game.submit_player_command(peer_id, {"action": "action_press"}))
		else:
			actions.append(_game.submit_player_command(peer_id, {"action": "place_bomb"}))
	# Godot can report both edges in a tick for a real fast tap. Act once, then
	# release, preserving the event instead of dropping it or leaving it held.
	if data.action_released:
		actions.append(_game.submit_player_command(peer_id, {"action": "action_release"}))
	if actions.is_empty():
		var applied := result(true, "input_applied", "packet")
		applied["movement"] = movement
		return applied
	# Input frames may contain distinct actions. Report every outcome, including
	# partial success; an ability rejection never fabricates success for another.
	var final: Dictionary = actions[-1].duplicate(true)
	for outcome in actions:
		if not outcome.accepted:
			final = outcome.duplicate(true)
			break
	final["actions"] = actions
	final["movement"] = movement
	return final
