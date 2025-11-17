extends Node

# Client stub for server project
# Provides RPC endpoints that server can call

# Client sends these to server (stubs)
@rpc("any_peer", "call_remote", "reliable")
func authenticate_request(_username: String, _password: String):
	pass

@rpc("any_peer", "call_remote", "reliable")
func register_request(_username: String, _password: String):
	pass

@rpc("any_peer", "call_remote", "unreliable")
func send_player_input(_input_data: Dictionary):
	pass

# Client receives these from server
@rpc("any_peer", "call_remote", "reliable")
func auth_response(_data: Dictionary):
	pass

@rpc("any_peer", "call_remote", "reliable")
func register_response(_data: Dictionary):
	pass

@rpc("any_peer", "call_remote", "unreliable")
func ai_debug_update(_debug_data: Dictionary):
	pass

@rpc("any_peer", "call_remote", "unreliable")
func receive_state(_state: Dictionary):
	pass

@rpc("any_peer", "call_remote", "unreliable")
func bomb_safety_update(_safety_data: Dictionary):
	# Stub - actual implementation on client
	pass
