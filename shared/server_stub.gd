extends Node

# Server stub for client project
# Provides RPC endpoints that client can call

func _ready():
	print("[Client] ServerMain stub RPC config:", get_script().get_rpc_config())

@warning_ignore("unused_parameter")
@rpc("any_peer", "call_remote", "reliable")
func authenticate_request(username: String, password: String):
	pass

@warning_ignore("unused_parameter")
@rpc("any_peer", "call_remote", "reliable")
func register_request(username: String, password: String):
	pass

@warning_ignore("unused_parameter")
@rpc("any_peer", "call_remote", "unreliable")
func send_player_input(input_data: Dictionary):
	pass

# Client-side methods (stubs to match RPC indices with main_client.gd)
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
