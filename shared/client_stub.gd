extends Node

# Client stub for server project
# Provides RPC endpoints that server can call

# Server-side methods (stubs to match RPC indices with main_server.gd)
@rpc("any_peer", "call_remote", "reliable")
func authenticate_request(_username: String, _password: String):
	# Stub - actual implementation on server
	pass

@rpc("any_peer", "call_remote", "reliable")
func register_request(_username: String, _password: String):
	# Stub - actual implementation on server
	pass

@rpc("any_peer", "call_remote", "unreliable")
func send_player_input(_input_data: Dictionary):
	# Stub - actual implementation on server
	pass

# Client-side methods (real implementations)
@rpc("any_peer", "call_remote", "reliable")
func auth_response(_data: Dictionary):
	# Stub - actual implementation on client
	pass

@rpc("any_peer", "call_remote", "reliable")
func register_response(_data: Dictionary):
	# Stub - actual implementation on client
	pass

@rpc("any_peer", "call_remote", "unreliable")
func receive_state(_state: Dictionary):
	# Stub - actual implementation on client
	pass
