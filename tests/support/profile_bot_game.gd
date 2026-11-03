extends "res://tests/support/fixture_game_instance.gd"

## Observe the real validated command boundary, without replacing its semantics.
var accepted_commands: Dictionary = {}
var refused_commands: Dictionary = {}
var participant_commands: Dictionary = {}

func _init() -> void:
	super()
	ServerBotManagerScript = preload("res://tests/support/profile_bot_manager.gd")

func submit_player_command(peer_id: int, command: Dictionary) -> Dictionary:
	var receipt: Dictionary = super(peer_id, command)
	var action: String = command.get("action", "")
	var key: String = action if receipt.accepted else "%s:%s" % [action, receipt.reason]
	var bucket: Dictionary = accepted_commands if receipt.accepted else refused_commands
	bucket[key] = int(bucket.get(key, 0)) + 1
	var identity := str(peer_id)
	if not participant_commands.has(identity): participant_commands[identity] = {}
	var own: Dictionary = participant_commands[identity]
	own[key] = int(own.get(key, 0)) + 1
	return receipt
