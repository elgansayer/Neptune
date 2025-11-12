extends Node

# Main client entry point
# Connects to server, handles authentication, and joins games

const Constants = preload("res://shared/constants.gd")

var peer: ENetMultiplayerPeer
var server_address = "127.0.0.1"  # localhost for testing
var connected = false
var authenticated = false
var username = ""

signal connection_succeeded
signal connection_failed
signal authentication_succeeded
signal authentication_failed(error: String)

func _ready():
	# Don't initialize client if running server scene
	if get_tree().current_scene and "server" in get_tree().current_scene.scene_file_path:
		return
	
	print("=== Bomberman Client Starting ===")
	multiplayer.connected_to_server.connect(_on_connected_to_server)
	multiplayer.connection_failed.connect(_on_connection_failed)
	multiplayer.server_disconnected.connect(_on_server_disconnected)
	print("[Client] RPC config:", get_script().get_rpc_config())

func connect_to_server(address: String = "127.0.0.1"):
	server_address = address
	peer = ENetMultiplayerPeer.new()
	
	print("[Client] Connecting to ", address, ":", Constants.SERVER_PORT)
	var error = peer.create_client(address, Constants.SERVER_PORT)
	
	if error != OK:
		push_error("Failed to create client: " + str(error))
		connection_failed.emit()
		return
	
	multiplayer.multiplayer_peer = peer

func _on_connected_to_server():
	print("[Client] Connected to server!")
	print("[Client] Multiplayer peer valid: ", multiplayer.multiplayer_peer != null)
	print("[Client] Multiplayer unique ID: ", multiplayer.get_unique_id())
	connected = true
	connection_succeeded.emit()

func _on_connection_failed():
	print("[Client] Connection failed!")
	connected = false
	connection_failed.emit()

func _on_server_disconnected():
	print("[Client] Disconnected from server")
	connected = false
	authenticated = false

# === Authentication ===

func login(user: String, password: String):
	if not connected:
		push_error("Not connected to server")
		return
	
	print("[Client] Attempting login as: ", user)
	username = user
	# Call RPC through ServerMain autoload
	ServerMain.rpc_id(1, "authenticate_request", user, password)

func register(user: String, password: String):
	if not connected:
		push_error("Not connected to server")
		return
	
	print("[Client] Attempting registration: ", user)
	# Call RPC through ServerMain autoload
	ServerMain.rpc_id(1, "register_request", user, password)

# === RPC Handlers ===

# Client sends these to server (stubs)
@rpc("any_peer", "call_remote", "reliable")
func authenticate_request(_username: String, _password: String):
	pass # Stub - actual implementation on server

@rpc("any_peer", "call_remote", "reliable")
func register_request(_username: String, _password: String):
	pass # Stub - actual implementation on server

@rpc("any_peer", "call_remote", "unreliable")
func send_player_input(_input_data: Dictionary):
	pass # Stub - actual implementation on server

# Client receives these from server authority
@rpc("any_peer", "call_remote", "reliable")
func auth_response(data: Dictionary):
	if data.success:
		print("[Client] Authentication successful!")
		authenticated = true
		username = data.username
		authentication_succeeded.emit()
	else:
		print("[Client] Authentication failed: ", data.get("error", "Unknown error"))
		authenticated = false
		authentication_failed.emit(data.get("error", "Unknown error"))

@rpc("any_peer", "call_remote", "reliable")
func register_response(data: Dictionary):
	if data.success:
		print("[Client] Registration successful!")
	else:
		print("[Client] Registration failed: ", data.get("error", "Unknown error"))

@rpc("any_peer", "call_remote", "unreliable")
func receive_state(state: Dictionary):
	# Forward to active game view scene
	var game_view = get_tree().current_scene
	if game_view and game_view.has_method("update_game_state"):
		game_view.update_game_state(state)

# === AI Bot Commands ===

# AI System removed - preparing for rebuild
# func request_spawn_bot(personality: int = -1):
# 	"""Request server to spawn an AI bot"""
# 	if not authenticated:
# 		push_error("Must be authenticated to spawn bots")
# 		return
# 	
# 	print("[Client] Requesting AI bot spawn (personality: ", personality, ")")
# 	get_node("/root/ServerMain").rpc_id(1, "spawn_ai_bot", personality)
