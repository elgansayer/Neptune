extends Node

# Client stub for server project
# Provides RPC endpoints that server can call

# Server-side methods (stubs to match RPC indices with main_server.gd)
@rpc("any_peer", "call_remote", "reliable")
func authenticate_request(_username: String, _password: String):
	pass

@rpc("any_peer", "call_remote", "reliable")
func register_request(_username: String, _password: String):
	pass

@rpc("any_peer", "call_remote", "unreliable")
func send_player_input(_input_data: Dictionary):
	pass

# Client-side methods (real implementations)
@warning_ignore("unused_parameter")
@rpc("any_peer", "call_remote", "reliable")
func auth_response(data: Dictionary):
	pass

@warning_ignore("unused_parameter")
@rpc("any_peer", "call_remote", "reliable")
func register_response(data: Dictionary):
	pass

@warning_ignore("unused_parameter")
@rpc("any_peer", "call_remote", "unreliable")
func receive_state(state: Dictionary):
	pass
