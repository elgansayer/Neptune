extends Node

# Server stub for client project
# Provides RPC endpoints that client can call

@rpc("any_peer", "call_remote", "reliable")
func authenticate_request(username: String, password: String):
	if false:
		print(username, password)
	pass

@rpc("any_peer", "call_remote", "reliable")
func register_request(username: String, password: String):
	if false:
		print(username, password)
	pass

@rpc("any_peer", "call_remote", "unreliable")
func send_player_input(input_data: Dictionary):
	if false:
		print(input_data)
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
func ai_debug_update(_debug_data: Dictionary):
	# Stub - actual implementation on client
	pass

@rpc("any_peer", "call_remote", "unreliable")
func receive_state(_state: Dictionary):
	# Stub - actual implementation on client
	pass

@rpc("any_peer", "call_remote", "reliable")
func spawn_bot_request(personality: String = "BALANCED"):
	if false:
		print(personality)
	pass
