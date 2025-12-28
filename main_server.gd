extends "res://shared/rpc_interface.gd"

# Main server entry point
# Runs headless, manages all game instances, authentication, and lobbies

const Constants = preload("res://shared/constants.gd")
const GameInstanceScript = preload("res://game_instance.gd")

var peer: ENetMultiplayerPeer
var auth_service # Will be LocalBackend or PlayFabBackend
var lobby_manager
var active_games = {} # game_id -> GameInstance
var player_to_game = {} # peer_id -> game_id
var _initialized = false # Prevent duplicate initialization

func _ready():
	# Only initialize once
	if _initialized:
		return
	_initialized = true
	
	# Check if we're running in server mode
	# Server runs when: headless OR main_server.tscn is the main scene OR has server scene
	var is_headless = DisplayServer.get_name() == "headless"
	var current_scene = get_tree().current_scene
	var is_server_scene = current_scene and (current_scene.scene_file_path.contains("server") or current_scene == self)
	var is_login_screen = current_scene and current_scene.scene_file_path.contains("login")
	
	# If we're showing the login screen, we're the client - don't initialize server
	if not is_headless and is_login_screen:
		print("[ServerMain] Running in client mode (login screen), acting as RPC router only")
		return
	
	# If we're headless OR the server scene is loaded, we're the server
	if not is_headless and not is_server_scene:
		print("[ServerMain] Running in client mode, acting as RPC router only")
		return
	
	print("=== Bomberman Server Starting ===")
	print("[Server] Node name: ", name)
	print("[Server] Node path: ", get_path())
	
	# Validate RPC configuration
	var rpc_validation = validate_rpc_config()
	if rpc_validation["valid"]:
		print("[Server] ✅ RPC config valid: ", rpc_validation["rpc_count"], " methods")
	else:
		push_error("[Server] ❌ RPC config mismatch! Expected ", rpc_validation["expected_count"], " got ", rpc_validation["rpc_count"])
	print("[Server] RPC config:", get_script().get_rpc_config())
	
	# Load backend service (local SQLite for now)
	auth_service = load("res://auth/local_backend.gd").new()
	add_child(auth_service)
	
	# Load lobby manager
	lobby_manager = load("res://lobby/lobby_manager.gd").new()
	add_child(lobby_manager)
	
	# Start server
	peer = ENetMultiplayerPeer.new()
	var error = peer.create_server(Constants.SERVER_PORT, Constants.MAX_PLAYERS)
	if error != OK:
		push_error("Failed to start server: " + str(error))
		return
	
	multiplayer.multiplayer_peer = peer
	multiplayer.peer_connected.connect(_on_player_connected)
	multiplayer.peer_disconnected.connect(_on_player_disconnected)
	
	print("Server listening on port ", Constants.SERVER_PORT)
	print("Max players: ", Constants.MAX_PLAYERS)
	print("[Server] Multiplayer authority: ", multiplayer.is_server())
	print("[Server] Unique ID: ", multiplayer.get_unique_id())

func _on_player_connected(peer_id: int):
	print("[Server] Peer connected: ", peer_id)
	# Wait for authentication before doing anything

func _on_player_disconnected(peer_id: int):
	print("[Server] Peer disconnected: ", peer_id)
	# Clean up player from game if in one
	if player_to_game.has(peer_id):
		var game_id = player_to_game[peer_id]
		if active_games.has(game_id):
			active_games[game_id].remove_player(peer_id)
		player_to_game.erase(peer_id)
	# Clean up from lobby
	lobby_manager.remove_player(peer_id)

# === RPC Handlers (order matches shared/rpc_interface.gd) ===

# 1. Debug/Admin RPCs
func set_debug_timescale(timescale: float) -> void:
	# Clamp to sane range for debugging
	var clamped = clamp(timescale, 0.1, 10.0)
	Engine.time_scale = clamped
	print("[Server] Debug time_scale set to ", Engine.time_scale)

# 2. Client-to-Server Auth RPCs
func authenticate_request(username: String, password: String):
	var peer_id = multiplayer.get_remote_sender_id()
	print("[Server] *** AUTHENTICATE RPC RECEIVED ***")
	print("[Server] Authentication attempt from peer ", peer_id, ": ", username)
	print("[Server] Is server: ", multiplayer.is_server())
	
	var result = auth_service.authenticate(username, password)
	
	# Auto-register if user doesn't exist
	if not result.success and result.get("error") == "User not found":
		print("[Server] Auto-registering new user: ", username)
		result = auth_service.register_user(username, password)
		if result.success:
			result = auth_service.authenticate(username, password)
	
	if result.success:
		print("[Server] Authentication successful: ", username)
		lobby_manager.add_player(peer_id, username)
		# Send response back to client's ClientMain autoload
		get_node("/root/ClientMain").rpc_id(peer_id, "auth_response", {"success": true, "username": username})
		
		# Quick-start: Create or join a game immediately
		await get_tree().create_timer(0.1).timeout
		quick_start_game(peer_id, username)
	else:
		print("[Server] Authentication failed: ", result.get("error", "Unknown error"))
		get_node("/root/ClientMain").rpc_id(peer_id, "auth_response", {"success": false, "error": result.get("error", "Invalid credentials")})

func register_request(username: String, password: String):
	var peer_id = multiplayer.get_remote_sender_id()
	print("[Server] *** REGISTER_USER RPC RECEIVED ***")
	print("[Server] Registration attempt from peer ", peer_id, ": ", username)
	
	var result = auth_service.register_user(username, password)
	
	if result.success:
		print("[Server] Registration successful: ", username)
		get_node("/root/ClientMain").rpc_id(peer_id, "register_response", {"success": true})
	else:
		print("[Server] Registration failed: ", result.get("error", "Unknown error"))
		get_node("/root/ClientMain").rpc_id(peer_id, "register_response", {"success": false, "error": result.get("error", "Registration failed")})

# 3. Client-to-Server Game Input
func send_player_input(input_data: Dictionary):
	var peer_id = multiplayer.get_remote_sender_id()
	
	# Find the game this player is in
	if not player_to_game.has(peer_id):
		return
	
	var game_id = player_to_game[peer_id]
	if not active_games.has(game_id):
		return
	
	# Forward input to the game instance
	active_games[game_id].handle_player_input(peer_id, input_data)

# 4. Ping/Pong (latency measurement)
func ping(timestamp: int):
	var peer_id = multiplayer.get_remote_sender_id()
	# Respond immediately with pong, echoing the timestamp
	# Use unreliable for ping/pong as we don't want retransmissions affecting latency measurement
	get_node("/root/ClientMain").rpc_id(peer_id, "pong", timestamp)

# 5. Server-to-Client Auth Responses (stubs)
func auth_response(_data: Dictionary):
	pass # Stub - actual implementation on client

func register_response(_data: Dictionary):
	pass # Stub - actual implementation on client

# 6. Server-to-Client Game State (stubs)
func ai_debug_update(_debug_data: Dictionary):
	pass # Stub - clients receive this

func receive_state(_state: Dictionary):
	pass # Stub - actual implementation on client

func receive_initial_map(_map_data: Dictionary):
	pass # Stub - actual implementation on client

func bomb_safety_update(_safety_data: Dictionary):
	pass # Stub - actual implementation on client

# 7. Latency Response (stub)
func pong(_timestamp: int):
	pass # Stub - actual implementation on client

# 8. Gameplay Features
func spawn_bot_request(personality: String = "BALANCED"):
	var peer_id = multiplayer.get_remote_sender_id()
	if not player_to_game.has(peer_id):
		return
	var game_id = player_to_game[peer_id]
	if not active_games.has(game_id):
		return
	active_games[game_id].spawn_bot(personality)
	print("[Server] Peer ", peer_id, " requested bot (", personality, ") in ", game_id)

func test_farming_spot_broadcast():
	var peer_id = multiplayer.get_remote_sender_id()
	print("[Server] TEST: Peer ", peer_id, " requested farming spot search test (F8)")
	if not player_to_game.has(peer_id):
		print("[Server] TEST: Peer not in a game")
		return
	var game_id = player_to_game[peer_id]
	if not active_games.has(game_id):
		print("[Server] TEST: Game not found")
		return
	var game = active_games[game_id]
	if game.has_method("test_farming_spot_search"):
		game.test_farming_spot_search()
	else:
		print("[Server] TEST: GameInstance missing test method")

# Quick-start game system (no lobby for now)
func quick_start_game(peer_id: int, username: String):
	# For now, all players join the SAME shared game
	var shared_game_id = "shared_game"
	
	# Create shared game if it doesn't exist
	if not active_games.has(shared_game_id):
		print("[Server] Creating new shared game instance")
		# Use load() instead of preload const to avoid compile-time issues
		var GameInstanceClass = load("res://game_instance.gd")
		var new_game = GameInstanceClass.new()
		new_game.game_id = shared_game_id
		new_game.name = shared_game_id
		add_child(new_game)
		active_games[shared_game_id] = new_game
		
		# AI System removed - preparing for rebuild
		# Auto-spawn AI bots for testing (3 bots with different personalities)
		# print("[Server] Auto-spawning 3 AI bots for testing...")
		# game.call_deferred("add_ai_bot", 0)  # Balanced
		# game.call_deferred("add_ai_bot", 1)  # Aggressive
		# game.call_deferred("add_ai_bot", 2)  # Timid
	
	var game = active_games[shared_game_id]
	player_to_game[peer_id] = shared_game_id
	
	# Add player to the shared game (auto-assigns spawn point)
	game.add_player(peer_id, username)
	
	print("[Server] Player ", username, " joined shared game. Total players: ", game.players.size())

# (no-op) Debug forwarding not required; broadcast happens from AI tasks via ClientMain

# AI System removed - preparing for rebuild
# AI bot spawning disabled - see spawn_ai_bot_local() for local testing
# @rpc("any_peer", "call_remote", "reliable")
# func spawn_ai_bot(personality: int = -1):

# func spawn_ai_bot_local(game_id: String, personality: int = -1):
# 	"""Spawn AI bot directly (for testing/single-player)"""
# 	if not active_games.has(game_id):
# 		print("[Server] Game not found: ", game_id)
# 		return
# 	
# 	var game = active_games[game_id]
# 	game.add_ai_bot(personality)
# 	print("[Server] AI bot spawned in ", game_id, ". Total players: ", game.players.size())
