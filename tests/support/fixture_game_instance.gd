extends GameInstance

## Physics/rules are production code; fixtures do not register global UI commands.
func _init() -> void:
	bot_policy_seed = 424242

func _register_console_commands() -> void:
	pass
