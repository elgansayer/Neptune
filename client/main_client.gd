extends "res://shared/rpc_interface.gd"

# Main client entry point
# Connects to server, handles authentication, and joins games

const Constants = preload("res://shared/constants.gd")
const RuntimeConfig = preload("res://shared/runtime_config.gd")
const ProtocolNegotiation = preload("res://shared/network/protocol_negotiation.gd")
const ContentDownload = preload("res://shared/network/content_download.gd")

var _runtime_role := ""
var _server_port := 7777

var peer: ENetMultiplayerPeer
var server_address = "127.0.0.1" # localhost for testing
var connected = false
var authenticated = false
var protocol_gate: Node
var negotiated_protocol := 0
var last_connection_error := ""
var username = ""
var pending_initial_map: Dictionary = {} # Cache initial map until GameView is ready
var content_cache_root := "user://pack-cache"
var content_download
var _last_content_result := {}
var last_content_result: Dictionary:
	get: return _last_content_result.duplicate(true)

signal connection_succeeded
signal connection_failed
signal authentication_succeeded
signal authentication_failed(error: String)
signal latency_updated(latency_ms: int)
signal content_status_changed(result: Dictionary)
signal initial_map_received(map_data: Dictionary)
signal game_state_received(state: Dictionary)

var _ping_timer: Timer = null
var _last_ping_timestamp: int = 0
var current_latency_ms: int = 0

func _ready():
	var runtime := RuntimeConfig.read()
	if not runtime.error.is_empty():
		push_error(runtime.error)
		get_tree().quit(2)
		return
	_runtime_role = runtime.role
	_server_port = runtime.port
	if _runtime_role != "client":
		return
	
	print("=== Bomberman Client Starting ===")
	
	# Register console commands (client-side)
	call_deferred("_register_client_console_commands")
	
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
	protocol_gate = ProtocolNegotiation.new()
	add_child(protocol_gate)
	if protocol_gate.configure(multiplayer) != OK:
		push_error("Could not configure gameplay protocol negotiation")
		get_tree().quit(2)
		return
	protocol_gate.rejected.connect(func(_id: int, reason: String):
		last_connection_error = reason
		_on_connection_failed()
	)
	print("[Client] RPC config:", get_script().get_rpc_config())
	
	# Setup ping timer
	_ping_timer = Timer.new()
	_ping_timer.name = "PingTimer"
	_ping_timer.wait_time = 1.0 # Ping every second
	_ping_timer.one_shot = false
	_ping_timer.timeout.connect(_send_ping)
	add_child(_ping_timer)

func connect_to_server(address: String = "127.0.0.1"):
	if _runtime_role != "client":
		print("[Client] Ignoring connect_to_server outside client role")
		return

	server_address = address
	_reset_content()
	connected = false
	authenticated = false
	negotiated_protocol = 0
	pending_initial_map.clear()
	last_connection_error = ""
	peer = ENetMultiplayerPeer.new()
	
	print("[Client] Connecting to ", address, ":", _server_port)
	var error = peer.create_client(address, _server_port)
	
	if error != OK:
		push_error("Failed to create client: " + str(error))
		connection_failed.emit()
		return
	
	multiplayer.multiplayer_peer = peer

func _on_connected_to_server():
	negotiated_protocol = protocol_gate.selected_version(1)
	if negotiated_protocol == 0:
		last_connection_error = "protocol_not_negotiated"
		peer.close()
		_on_connection_failed()
		return
	print("[Client] Connected to server!")
	print("[Client] Protocol selected: ", negotiated_protocol)
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
	authenticated = false
	negotiated_protocol = 0
	pending_initial_map.clear()
	_reset_content(true)
	if last_connection_error.is_empty():
		last_connection_error = "transport_connection_failed"
	if _ping_timer:
		_ping_timer.stop()
	print("[Client] Connection refused: ", last_connection_error)
	connection_failed.emit()

func _on_server_disconnected():
	print("[Client] Disconnected from server")
	connected = false
	authenticated = false
	negotiated_protocol = 0
	pending_initial_map.clear()
	_reset_content(true)
	if _ping_timer:
		_ping_timer.stop()

# === Authentication ===

func login(user: String, password: String):
	if not connected:
		push_error("Not connected to server")
		return
	if content_download != null and content_download.receipt().state == "failed":
		_reset_content()
	
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
	if _runtime_role == "client" and (not connected or multiplayer.get_remote_sender_id() != 1): return
	if data.success:
		if content_download != null and content_download.receipt().state != "ready":
			cancel_content_download("content_auth_before_ready")
			return
		print("[Client] Authentication successful!")
		authenticated = true
		username = data.username
		authentication_succeeded.emit()
	else:
		print("[Client] Authentication failed: ", data.get("error", "Unknown error"))
		authenticated = false
		authentication_failed.emit(data.get("error", "Unknown error"))

func register_response(data: Dictionary):
	if _runtime_role == "client" and (not connected or multiplayer.get_remote_sender_id() != 1): return
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
	if not connected or not authenticated: return
	if _runtime_role == "client" and multiplayer.get_remote_sender_id() != 1: return
	if content_download != null and content_download.receipt().state != "ready": return
	game_state_received.emit(state.duplicate(true))
	# Forward to active game view scene - find GameView node in tree
	var game_view = _find_game_view()
	if game_view:
		game_view.update_game_state(state)

func receive_initial_map(map_data: Dictionary):
	if _runtime_role == "client" and (not connected or multiplayer.get_remote_sender_id() != 1): return
	var config = map_data.get("map_config", {})
	if content_download != null or (config is Dictionary and config.has("content")):
		if content_download == null:
			cancel_content_download("content_map_without_offer")
			return
		var verified: Dictionary = content_download.validate_initial_map(map_data)
		if not verified.accepted:
			cancel_content_download(verified.reason)
			return
	initial_map_received.emit(map_data.duplicate(true))
	# Initial map data sent reliably (TCP) to handle larger payload
	print("[ClientMain] Received initial map data with keys: ", map_data.keys())
	var game_view = _find_game_view()
	if game_view:
		game_view.update_game_state(map_data)
	else:
		# Cache the map data until GameView is ready
		pending_initial_map = map_data
		print("[ClientMain] Cached initial map data (GameView not ready yet)")

func content_message(message: Dictionary) -> void:
	# RPC routing is shared for identical checksums; only the authority may offer
	# bytes or change this client's selection. Peers never supply filesystem paths.
	if _runtime_role != "client" or not connected or multiplayer.get_remote_sender_id() != 1: return
	match message.get("type"):
		"offer":
			if authenticated or content_download != null:
				cancel_content_download("unexpected_content_offer")
				return
			content_download = ContentDownload.new(content_cache_root)
			content_download.outbound.connect(_send_content_message)
			content_download.status_changed.connect(_on_content_status)
			content_download.begin(message)
		"chunk":
			if content_download != null: content_download.receive(message)
		"failure":
			if content_download == null or not ContentDownload.exact_keys(message, ["type", "session_id", "reason"]): return
			if message.get("session_id") != content_download.session_id() or not message.get("reason") is String or message.reason.length() > 128: return
			if content_download.receipt().state != "failed": cancel_content_download(message.reason)

func _process(_delta: float) -> void:
	if content_download != null: content_download.tick()

func _send_content_message(message: Dictionary) -> void:
	if connected: ServerMain.rpc_id(1, "content_message", message)

func _on_content_status(result: Dictionary) -> void:
	_last_content_result = result.duplicate(true)
	content_status_changed.emit(result.duplicate(true))
	if result.state == "failed":
		authenticated = false
		pending_initial_map.clear()
		authentication_failed.emit(result.reason)

func cancel_content_download(reason: String = "content_cancelled") -> void:
	# Once ready was sent, the authority may already have admitted this actor.
	# Closing that transport is required before a retry can clear local selection.
	var must_reconnect: bool = authenticated or (content_download != null and content_download.receipt().state == "ready") or reason == "content_auth_before_ready"
	var closing_peer := peer
	if must_reconnect:
		connected = false
		negotiated_protocol = 0
		last_connection_error = reason
		if _ping_timer: _ping_timer.stop()
	if content_download != null:
		content_download.cancel(reason)
	else:
		_last_content_result = {"accepted": false, "state": "failed", "reason": reason}
		content_status_changed.emit(_last_content_result.duplicate(true))
		authentication_failed.emit(reason)
	authenticated = false
	pending_initial_map.clear()
	if must_reconnect and closing_peer != null: closing_peer.close()

func _reset_content(preserve_failure: bool = false) -> void:
	# Disconnects abandon only the transient buffer. Independently verified immutable
	# releases remain cached and can be reused on another exact compatible offer.
	var failure: Dictionary = _last_content_result.duplicate(true) if preserve_failure and _last_content_result.get("state") == "failed" else {}
	if content_download != null:
		if content_download.outbound.is_connected(_send_content_message):
			content_download.outbound.disconnect(_send_content_message)
		if content_download.status_changed.is_connected(_on_content_status):
			content_download.status_changed.disconnect(_on_content_status)
		content_download.cancel("content_connection_reset")
	content_download = null
	_last_content_result = failure

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

func _register_client_console_commands() -> void:
	"""Register console commands on the client side"""
	if not has_node("/root/LimboConsole"):
		print("[Client] ⚠️ LimboConsole not found, skipping command registration")
		return
	
	print("[Client] 🎮 Loading console commands...")
	var console_commands = load("res://scripts/console_commands.gd").new()
	console_commands.name = "ConsoleCommands"
	add_child(console_commands)
	
	# Pass null - commands will find game_instance dynamically
	console_commands.register_all_commands(null)
	print("[Client] ✅ Console commands registered!")
