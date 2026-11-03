@tool
extends BTAction

## Clear an owned remote bomb after reaching a refuge outside all observed
## blast envelopes. Selection stays inside the normal strategic reaction gate.
func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player", null)
	var world = blackboard.get_var("game_instance", null)
	var manager = blackboard.get_var("ai_manager", null)
	if not is_instance_valid(player) or world == null or manager == null:
		return FAILURE
	if player.is_dead or player.bomb_type != ServerBomb.BOMB_TYPE_REMOTE:
		return FAILURE
	var cell: Vector2i = player.get_tile_position()
	# A detonation is optional; never interrupt retreat to trigger from an
	# observed current or future blast lane, including shortened chains.
	if manager.get_current_threat_matrix().has("%d,%d" % [cell.x, cell.y]):
		return FAILURE
	var found := false
	for bomb in world.bombs.values():
		if is_instance_valid(bomb) and not bomb.has_exploded \
				and bomb.owner_id == player.player_id \
				and bomb.bomb_type == ServerBomb.BOMB_TYPE_REMOTE \
				and bomb.bomb_state == ServerBomb.BombState.PLANTED:
			found = true
			break
	if not found or not player.has_method("request_remote_detonation"):
		return FAILURE
	var receipt: Dictionary = player.request_remote_detonation()
	if not receipt.accepted:
		blackboard.set_var("last_command_rejection", receipt.reason)
		return FAILURE
	player.set_input(0, 0)
	blackboard.set_var("last_remote_detonation", receipt.bomb_ids.duplicate())
	return SUCCESS
