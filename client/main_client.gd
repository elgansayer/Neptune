extends "res://shared/rpc_interface.gd"

# Main client entry point
# Connects to server, handles authentication, and joins games

const Constants = preload("res://shared/constants.gd")

var peer: ENetMultiplayerPeer
var server_address = "127.0.0.1" # localhost for testing
var connected = false
var authenticated = false
var username = ""
var pending_initial_map: Dictionary = {} # Cache initial map until GameView is ready

signal connection_succeeded
signal connection_failed
signal authentication_succeeded
signal authentication_failed(error: String)
signal latency_updated(latency_ms: int)

var _ping_timer: Timer = null
var _last_ping_timestamp: int = 0
var current_latency_ms: int = 0

func _ready():
	# Don't initialize client if running headless (server mode)
	if DisplayServer.get_name() == "headless":
		return
	
	# Don't initialize client if running server scene
	if get_tree().current_scene and "server" in get_tree().current_scene.scene_file_path:
		return
	
	print("=== Bomberman Client Starting ===")
	
	# Validate RPC configuration
	var rpc_validation = validate_rpc_config()
	if rpc_validation["valid"]:
		print("[Client] ✅ RPC config valid: ", rpc_validation["rpc_count"], " methods")
	else:
		push_error("[Client] ❌ RPC config mismatch! Expected ", rpc_validation["expected_count"], " got ", rpc_validation["rpc_count"])
	print("[Client] RPC config:", get_script().get_rpc_config())
	
	multiplayer.connected_to_server.connect(_on_connected_to_server)
	multiplayer.connection_failed.connect(_on_connection_failed)
	multiplayer.server_disconnected.connect(_on_server_disconnected)
	print("[Client] RPC config:", get_script().get_rpc_config())
	
	# Setup ping timer
	_ping_timer = Timer.new()
	_ping_timer.name = "PingTimer"
	_ping_timer.wait_time = 1.0 # Ping every second
	_ping_timer.one_shot = false
	_ping_timer.timeout.connect(_send_ping)
	add_child(_ping_timer)

func connect_to_server(address: String = "127.0.0.1"):
	# Safety check: Never connect as client if we are the headless server
	if DisplayServer.get_name() == "headless":
		print("[Client] Ignoring connect_to_server call in headless mode")
		return

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
	
	# Start pinging
	if _ping_timer:
		_ping_timer.start()

func _on_connection_failed():
	print("[Client] Connection failed!")
	connected = false
	connection_failed.emit()

func _on_server_disconnected():
	print("[Client] Disconnected from server")
	connected = false
	authenticated = false
	if _ping_timer:
		_ping_timer.stop()

# === Authentication ===

func login(user: String, password: String):
	if not connected:
		push_error("Not connected to server")
		return
	
	print("[Client] Attempting login as: ", user)
	username = user
	# Call RPC through ServerMain autoload (exists on both client and server)
	ServerMain.rpc_id(1, "authenticate_request", user, password)

func register(user: String, password: String):
	if not connected:
		push_error("Not connected to server")
		return
	
	print("[Client] Attempting registration: ", user)
	# Call RPC through ServerMain autoload (exists on both client and server)
	ServerMain.rpc_id(1, "register_request", user, password)

# === RPC Handlers (order matches shared/rpc_interface.gd) ===

# 1. Debug/Admin RPCs (stubs)
func set_debug_timescale(_timescale: float):
	pass # Stub - actual implementation on server

# 2. Client-to-Server Auth RPCs (stubs)
func authenticate_request(_username: String, _password: String):
	pass # Stub - actual implementation on server

func register_request(_username: String, _password: String):
	pass # Stub - actual implementation on server

# 3. Client-to-Server Game Input (stub)
func send_player_input(_input_data: Dictionary):
	pass # Stub - actual implementation on server

# 4. Ping/Pong (stub)
func ping(_timestamp: int):
	pass # Stub - actual implementation on server

# 5. Server-to-Client Auth Responses
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

func register_response(data: Dictionary):
	if data.success:
		print("[Client] Registration successful!")
	else:
		print("[Client] Registration failed: ", data.get("error", "Unknown error"))

# 6. Server-to-Client Game State
func ai_debug_update(debug_data: Dictionary):
	"""Receive AI debug data from server"""
	var game_view = _find_game_view()
	if game_view and game_view.has_method("update_ai_debug"):
		game_view.update_ai_debug(debug_data)

func receive_state(state: Dictionary):
	# Forward to active game view scene - find GameView node in tree
	var game_view = _find_game_view()
	if game_view:
		game_view.update_game_state(state)

func receive_initial_map(map_data: Dictionary):
	# Initial map data sent reliably (TCP) to handle larger payload
	print("[ClientMain] Received initial map data with keys: ", map_data.keys())
	var game_view = _find_game_view()
	if game_view:
		game_view.update_game_state(map_data)
	else:
		# Cache the map data until GameView is ready
		pending_initial_map = map_data
		print("[ClientMain] Cached initial map data (GameView not ready yet)")

func bomb_safety_update(safety_data: Dictionary):
	# Forward bomb safety data to current GameView
	print("[ClientMain] RPC bomb_safety_update received with %d tiles" % safety_data.size())
	var game_view = _find_game_view()
	if game_view:
		print("[ClientMain] Forwarding to GameView")
		game_view.bomb_safety_update(safety_data)
	else:
		print("[ClientMain] GameView not ready yet")

# 7. Latency Response
func pong(timestamp: int):
	var now = Time.get_ticks_msec()
	var rtt = now - timestamp
	# Latency is half of RTT
	current_latency_ms = int(rtt / 2.0)
	latency_updated.emit(current_latency_ms)
	# print("[Client] Latency: %d ms" % current_latency_ms)

# 8. Gameplay Features (stubs)
func spawn_bot_request(_personality: String = "BALANCED"):
	pass # Stub - actual implementation on server

func test_farming_spot_broadcast():
	pass # Stub - actual implementation on server

# === Helper Functions ===

func get_pending_initial_map() -> Dictionary:
	"""Get and clear pending initial map data (called by GameView when ready)"""
	var data = pending_initial_map
	pending_initial_map = {}
	return data

func _find_game_view() -> Node:
	"""Find GameView node in scene tree - handles both direct scene and nested cases"""
	var current = get_tree().current_scene
	if current and current.has_method("update_game_state"):
		return current
	# Search for GameView by name in current scene's children
	if current:
		var game_view = current.find_child("GameView", true, false)
		if game_view and game_view.has_method("update_game_state"):
			return game_view
	# Also check direct children of root
	for child in get_tree().root.get_children():
		if child.name == "GameView" and child.has_method("update_game_state"):
			return child
	return null

func _send_ping():
	if not connected:
		return
	
	var now = Time.get_ticks_msec()
	_last_ping_timestamp = now
	# Call ping on server (ID 1)
	get_node("/root/ServerMain").rpc_id(1, "ping", now)

# === AI Bot Commands ===

func request_spawn_bot(personality: String = "BALANCED"):
	"""Request server to spawn an AI bot"""
	if not authenticated:
		push_error("Must be authenticated to spawn bots")
		return
	
	print("[Client] Requesting AI bot spawn (personality: ", personality, ")")
	get_node("/root/ServerMain").rpc_id(1, "spawn_bot_request", personality)
