extends Node
class_name RPCInterface

## Shared RPC interface for client-server communication
## Ensures identical RPC method ordering across ClientMain and ServerMain
## All @rpc declarations MUST be in the same order in both files

# === RPC Methods (must match order exactly) ===

# 1. Debug/Admin RPCs
@rpc("any_peer", "call_remote", "reliable")
func set_debug_timescale(_timescale: float) -> void:
	pass

# 2. Client-to-Server Auth RPCs
@rpc("any_peer", "call_remote", "reliable")
func authenticate_request(_username: String, _password: String):
	pass

@rpc("any_peer", "call_remote", "reliable")
func register_request(_username: String, _password: String):
	pass

# 3. Client-to-Server Game Input
@rpc("any_peer", "call_remote", "unreliable")
func send_player_input(_input_data: Dictionary):
	pass

# 4. Ping/Pong (latency measurement)
@rpc("any_peer", "call_remote", "unreliable")
func ping(_timestamp: int):
	pass

# 5. Server-to-Client Auth Responses
@rpc("any_peer", "call_remote", "reliable")
func auth_response(_data: Dictionary):
	pass

@rpc("any_peer", "call_remote", "reliable")
func register_response(_data: Dictionary):
	pass

# 6. Server-to-Client Game State
@rpc("any_peer", "call_remote", "unreliable")
func ai_debug_update(_debug_data: Dictionary):
	pass

@rpc("any_peer", "call_remote", "unreliable")
func receive_state(_state: Dictionary):
	pass

@rpc("any_peer", "call_remote", "reliable")
func receive_initial_map(_map_data: Dictionary):
	pass

@rpc("any_peer", "call_remote", "unreliable")
func bomb_safety_update(_safety_data: Dictionary):
	pass

# 7. Latency Response
@rpc("authority", "call_remote", "unreliable")
func pong(_timestamp: int):
	pass

# 8. Gameplay Features
@rpc("any_peer", "call_remote", "reliable")
func spawn_bot_request(_personality: String = "BALANCED"):
	pass

@rpc("any_peer", "call_remote", "reliable")
func test_farming_spot_broadcast():
	pass

# 9. Authority-controlled immutable content transfer and readiness.
@rpc("any_peer", "call_remote", "reliable")
func content_message(_message: Dictionary):
	pass

## Validation function to check RPC configuration
func validate_rpc_config() -> Dictionary:
	var config = get_script().get_rpc_config()
	var expected_count = 15  # Total number of @rpc methods
	var is_valid = config.size() == expected_count
	
	return {
		"valid": is_valid,
		"rpc_count": config.size(),
		"expected_count": expected_count,
		"config": config
	}
