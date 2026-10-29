extends RefCounted

var _authority: WeakRef
var _actor: WeakRef
var _source
var _peer_id: int

func _init(authority: Node, actor: Node, source) -> void:
	_authority = weakref(authority)
	_actor = weakref(actor)
	_peer_id = actor.peer_id
	_source = source

func invoke(command: Dictionary) -> Dictionary:
	var game = _authority.get_ref()
	var actor = _actor.get_ref()
	if not is_instance_valid(game) or not is_instance_valid(actor) or game.players.get(_peer_id) != actor:
		return {"accepted": false, "reason": "unknown_player", "action": command.get("action", ""), "bomb_ids": []}
	var result: Dictionary = game.submit_player_command(_peer_id, command)
	if result.accepted and command.get("action") not in ["move", "action_release"]:
		_source.mark_dirty()
	return result.duplicate(true)

func contacts() -> Array:
	var game = _authority.get_ref()
	var actor = _actor.get_ref()
	if not is_instance_valid(game) or not is_instance_valid(actor) or game.players.get(_peer_id) != actor:
		return []
	return actor.get_observed_contacts()
