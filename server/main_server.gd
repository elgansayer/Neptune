extends Node

# Main server entry point
# Runs headless, manages all game instances, authentication, and lobbies

const Constants = preload("res://shared/constants.gd")
const GameInstance = preload("res://server/game_instance.gd")

var peer: ENetMultiplayerPeer
var auth_service  # Will be LocalBackend or PlayFabBackend
var lobby_manager
var active_games = {}  # game_id -> GameInstance
var player_to_game = {}  # peer_id -> game_id

func _ready():
	# Only initialize server if we're running the server scene
	# (not when loaded as autoload in client)
	await get_tree().process_frame
	if get_tree().current_scene and "server" not in get_tree().current_scene.scene_file_path:
		print("[ServerMain] Not running server scene, skipping initialization")
		return
	
	print("=== Bomberman Server Starting ===")
	print("[Server] Node name: ", name)
	print("[Server] Node path: ", get_path())
	
	# Load backend service (local SQLite for now)
	auth_service = load("res://server/auth/local_backend.gd").new()
	add_child(auth_service)
	
	# Load lobby manager
	lobby_manager = load("res://server/lobby/lobby_manager.gd").new()
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

# === RPC Handlers ===

@rpc("any_peer", "call_remote", "reliable")
func authenticate(username: String, password: String):
	var peer_id = multiplayer.get_remote_sender_id()
	print("[Server] *** AUTHENTICATE RPC RECEIVED ***")
	print("[Server] Authentication attempt from peer ", peer_id, ": ", username)
	print("[Server] Is server: ", multiplayer.is_server())
	
	var result = auth_service.authenticate(username, password)
	
	if result.success:
		print("[Server] Authentication successful: ", username)
		lobby_manager.add_player(peer_id, username)
		get_node("/root/ClientMain").rpc_id(peer_id, "auth_response", {"success": true, "username": username})
		
		# Quick-start: Create or join a game immediately
		await get_tree().create_timer(0.1).timeout
		quick_start_game(peer_id, username)
	else:
		print("[Server] Authentication failed: ", result.get("error", "Unknown error"))
		get_node("/root/ClientMain").rpc_id(peer_id, "auth_response", {"success": false, "error": result.get("error", "Invalid credentials")})

@rpc("any_peer", "call_remote", "reliable")
func register_user(username: String, password: String):
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

# Client-side stubs (will never be called on server)
@rpc("authority", "call_local", "reliable")
func auth_response(_data: Dictionary):
	pass

@rpc("authority", "call_local", "reliable")
func register_response(_data: Dictionary):
	pass

@rpc("any_peer", "call_remote", "unreliable")
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

# Quick-start game system (no lobby for now)
func quick_start_game(peer_id: int, username: String):
	# For now, just create a new game for each player
	var game_id = "game_" + str(Time.get_ticks_msec())
	var game = GameInstance.new()
	game.game_id = game_id
	game.name = game_id
	add_child(game)
	
	active_games[game_id] = game
	player_to_game[peer_id] = game_id
	
	# Spawn player at a starting position
	var spawn_pos = Vector2(64 * 1.5, 64 * 1.5)  # Top-left spawn
	game.add_player(peer_id, username, spawn_pos)
	
	print("[Server] Started game ", game_id, " for player ", username)

