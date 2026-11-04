extends "res://shared/rpc_interface.gd"

# Main server entry point
# Runs headless, manages all game instances, authentication, and lobbies

const Constants = preload("res://shared/constants.gd")
const GameInstanceScript = preload("res://game_instance.gd")
const RuntimeConfig = preload("res://shared/runtime_config.gd")
const ProtocolNegotiation = preload("res://shared/network/protocol_negotiation.gd")
const ContentDownload = preload("res://shared/network/content_download.gd")
const PackArchive = preload("res://shared/content/pack_archive.gd")

var peer: MultiplayerPeer
var auth_service # Will be LocalBackend or PlayFabBackend
var lobby_manager
var active_games = {} # game_id -> GameInstance
var player_to_game = {} # peer_id -> game_id
var _initialized = false # Prevent duplicate initialization
var protocol_gate: Node
var _server_room_options := {}
var _content_offer_template := {}
var _content_archives := {}
var _pending_content := {} # Account-authenticated peers; never game participants yet.
var _finished_room_serial := 0

func _ready():
	# RPC ownership belongs to the autoload, never a second scene instance.
	if self != get_node("/root/ServerMain"):
		return
	# Only initialize once
	if _initialized:
		return
	_initialized = true
	
	var runtime := RuntimeConfig.read()
	if not runtime.error.is_empty():
		push_error(runtime.error)
		get_tree().quit(2)
		return
	if runtime.role != "server":
		print("[ServerMain] Runtime role: ", runtime.role, "; RPC router only")
		return
	# GameConfig/LimboConsole autoloads must exist before preparing the room.
	call_deferred("_start_server", runtime)

func _start_server(runtime: Dictionary) -> void:
	_server_room_options = runtime.duplicate(true)
	
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
	var prepared := _prepare_shared_game(runtime)
	if not prepared.accepted:
		print("[Server] Room setup refused: ", prepared.reason)
		if prepared.has("field"):
			print("[Server] Content diagnostic: ", JSON.stringify(prepared))
		get_tree().quit(2)
		return
	
	# Start server
	var listener := preload("res://shared/network/transport.gd").server(runtime.transport, runtime.port, Constants.MAX_CONNECTED_PEERS)
	peer = listener.peer
	var error: int = listener.error
	if error != OK:
		push_error("Failed to start server: " + str(error))
		get_tree().quit(1)
		return
	
	protocol_gate = ProtocolNegotiation.new()
	add_child(protocol_gate)
	if protocol_gate.configure(multiplayer) != OK:
		push_error("Could not configure gameplay protocol negotiation")
		get_tree().quit(2)
		return
	# All traffic is client <-> authority. Do not relay other clients as new peers.
	multiplayer.server_relay = false
	protocol_gate.rejected.connect(func(id: int, reason: String):
		print("[Server] Protocol rejected: ", id, " ", reason)
	)
	multiplayer.peer_connected.connect(_on_player_connected)
	multiplayer.peer_disconnected.connect(_on_player_disconnected)
	multiplayer.multiplayer_peer = peer
	
	print("Server listening on port ", runtime.port)
	print("Max connected peers: ", Constants.MAX_CONNECTED_PEERS)
	print("[Server] Multiplayer authority: ", multiplayer.is_server())
	print("[Server] Unique ID: ", multiplayer.get_unique_id())

func _on_player_connected(peer_id: int):
	print("[Server] Peer connected: ", peer_id)
	print("[Server] Protocol selected: ", peer_id, " ", protocol_gate.selected_version(peer_id))
	# Wait for authentication before doing anything

func _on_player_disconnected(peer_id: int):
	print("[Server] Peer disconnected: ", peer_id)
	_clear_content_pending(peer_id)
	# Clean up player from game if in one
	if player_to_game.has(peer_id):
		var game_id = player_to_game[peer_id]
		if active_games.has(game_id):
			active_games[game_id].remove_player(peer_id)
		player_to_game.erase(peer_id)
		# Completed rooms are retained only while their original clients remain.
		if game_id != "shared_game" and active_games.has(game_id) and not game_id in player_to_game.values():
			active_games[game_id].queue_free()
			active_games.erase(game_id)
	# The last human stops the room immediately, including all bot tasks. A fresh
	# waiting authority is installed outside physics; no unattended countdowns.
	if active_games.has("shared_game"):
		var current = active_games["shared_game"]
		if _room_humans(current).is_empty():
			current.process_mode = Node.PROCESS_MODE_DISABLED
			call_deferred("_clear_empty_shared_room", current)
	# Clean up from lobby
	lobby_manager.remove_player(peer_id)

# === RPC Handlers (order matches shared/rpc_interface.gd) ===

# 1. Debug/Admin RPCs
func set_debug_timescale(timescale: float) -> void:
	# Remote peers never control public simulation timing. This remains a
	# trusted local diagnostic only; casual lifecycle uses simulation durations.
	if multiplayer.get_remote_sender_id() != 0: return
	# Clamp to sane range for debugging
	var clamped = clamp(timescale, 0.1, 10.0)
	Engine.time_scale = clamped
	print("[Server] Debug time_scale set to ", Engine.time_scale)

# 2. Client-to-Server Auth RPCs
func authenticate_request(username: String, password: String):
	var peer_id = multiplayer.get_remote_sender_id()
	if peer_id <= 1 or not multiplayer.is_server(): return
	if _pending_content.has(peer_id):
		_fail_content(peer_id, "content_already_pending")
		return
	if player_to_game.has(peer_id):
		get_node("/root/ClientMain").rpc_id(peer_id, "auth_response", {"success": false, "error": "already_admitted"})
		return
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
		if not _content_offer_template.is_empty():
			_begin_content(peer_id, username)
			return
		var admission := quick_start_game(peer_id, username)
		if admission.accepted:
			lobby_manager.add_player(peer_id, username)
			get_node("/root/ClientMain").rpc_id(peer_id, "auth_response", {"success": true, "username": username, "room": active_games["shared_game"].get_room_capacity()})
		else:
			get_node("/root/ClientMain").rpc_id(peer_id, "auth_response", {"success": false, "error": admission.reason})
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
	_dispatch_room_input(multiplayer.get_remote_sender_id(), input_data)

func _dispatch_room_input(peer_id: int, input_data: Dictionary) -> Dictionary:
	if not player_to_game.has(peer_id): return {"accepted": false, "reason": "not_admitted"}
	var game_id = player_to_game[peer_id]
	if not active_games.has(game_id): return {"accepted": false, "reason": "unknown_room"}
	var game = active_games[game_id]
	var epoch = input_data.get("round_epoch")
	if not epoch is int or epoch != game.round_epoch: return {"accepted": false, "reason": "stale_round"}
	if not game.match_active: return {"accepted": false, "reason": "match_inactive"}
	# The transport envelope is checked here; the unchanged command dispatcher
	# continues to reject every unknown gameplay/action field.
	var packet: Dictionary = input_data.duplicate()
	packet.erase("round_epoch")
	return game.handle_player_input(peer_id, packet)

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

func _clear_empty_shared_room(authority: Node) -> void:
	if not is_instance_valid(authority) or active_games.get("shared_game") != authority: return
	var humans := _room_humans(authority)
	if not humans.is_empty():
		# A new visitor may authenticate before the deferred cleanup. Transfer
		# their membership along with the fresh arena rather than leaving a frozen room.
		if authority.get_round_result().is_empty():
			authority.match_active = true
			authority.end_match("empty_room")
		authority.results_time_remaining = 0.0
		_advance_shared_round(authority)
		return
	if not _pending_content.is_empty(): return
	var built := _build_shared_game(_server_room_options, authority)
	if built.accepted: _install_shared_game(built.game, authority)
	else: push_error("Empty room cleanup failed: " + str(built.reason))

func _room_humans(game: Node) -> Dictionary:
	var humans := {}
	for id in player_to_game:
		if player_to_game[id] != "shared_game": continue
		if game.spectators.has(id): humans[id] = game.spectators[id]
		elif game.players.has(id) and not game.players[id].is_bot:
			humans[id] = game.players[id].username
	return humans

func _build_shared_game(runtime: Dictionary, previous: Node = null) -> Dictionary:
	var new_game = GameInstanceScript.new()
	new_game.game_id = "shared_game"
	new_game.name = "shared_game"
	new_game.round_epoch = _finished_room_serial + 1
	new_game.continuous_room = true
	new_game.countdown_time = 0.0
	new_game.countdown_duration = float(runtime.get("room_countdown", 3))
	new_game.results_duration = float(runtime.get("room_intermission", 5))
	new_game.match_duration = float(runtime.get("room_duration", 180))
	new_game.match_time_remaining = new_game.match_duration
	# Keep the normal final-minute hurry phase; short trusted demo/CI battles
	# retain the same final-third relationship instead of starting in hurry.
	new_game.hurry_trigger_time = minf(60.0, new_game.match_duration / 3.0)
	new_game.room_map_path = runtime.get("room_map", "")
	new_game.room_pack_paths = runtime.get("room_pack_paths", []).duplicate()
	new_game.room_arena_id = runtime.get("room_arena", "")
	new_game.room_capacity_request = {"seats": runtime.get("room_seats", 0), "preset_limit": runtime.get("room_preset_limit", Constants.MAX_MATCH_SEATS)}
	new_game.room_bot_fill_request = {"target": runtime.get("room_fill_to", 4), "default_target": runtime.get("room_fill_default", true), "personality": runtime.get("room_bot_personality", "BALANCED")}
	if previous != null:
		new_game.room_map_snapshot = previous.room_initial_map_data.duplicate(true)
		new_game.spawn_seed = previous.spawn_seed
	add_child(new_game)
	if not new_game.room_setup_result.accepted:
		var refused: Dictionary = new_game.room_setup_result.duplicate(true)
		new_game.queue_free()
		return refused
	if previous != null and (new_game.room_content_lock != previous.room_content_lock or new_game.room_content_selection != previous.room_content_selection):
		new_game.queue_free()
		return {"accepted": false, "reason": "round_content_identity_changed"}
	new_game.next_round_requested.connect(_on_next_round_requested)
	return {"accepted": true, "game": new_game}

func _install_shared_game(new_game: Node, previous: Node = null) -> void:
	if previous != null:
		previous.process_mode = Node.PROCESS_MODE_DISABLED
		previous.get_parent().remove_child(previous)
		previous.queue_free()
	_finished_room_serial = new_game.round_epoch
	active_games["shared_game"] = new_game
	new_game.name = "shared_game"
	# Existing console callables retain their server lifetime and change target.
	new_game._do_register_console_commands()

func _prepare_shared_game(runtime: Dictionary = {}) -> Dictionary:
	var previous = active_games.get("shared_game")
	if previous != null:
		# Active clients keep their result for the configured results interval;
		# new visitors join that same room as spectators rather than stranding it.
		if previous.get_round_result().is_empty() or not _room_humans(previous).is_empty() or not _pending_content.is_empty():
			return {"accepted": true, "reason": "room_prepared"}
	var built := _build_shared_game(runtime, previous)
	if not built.accepted: return built
	var sharing := _prepare_content_offers(built.game)
	if not sharing.accepted:
		built.game.queue_free()
		return sharing
	_install_shared_game(built.game, previous)
	return {"accepted": true, "reason": "room_prepared"}

func _on_next_round_requested(authority: Node) -> void:
	# Authority signals run during physics. Replacement creates collision bodies
	# only after the query flush, and verifies its source again at that boundary.
	call_deferred("_advance_shared_round", authority)

func _advance_shared_round(authority: Node) -> Dictionary:
	if not is_instance_valid(authority) or active_games.get("shared_game") != authority:
		return {"accepted": false, "reason": "stale_authority"}
	if authority.get_round_result().is_empty():
		return {"accepted": false, "reason": "round_not_finished"}
	if authority.continuous_room and authority.results_time_remaining > 0.0:
		return {"accepted": false, "reason": "intermission_active"}
	if not _pending_content.is_empty():
		# Transfers are bounded by the existing wall-clock timeout; preserve the
		# exact current content transaction until readiness/failure resolves it.
		authority._restart_requested = false
		return {"accepted": false, "reason": "content_not_ready"}
	var humans := _room_humans(authority)
	var built := _build_shared_game(_server_room_options, authority)
	if not built.accepted:
		push_error("Round handoff failed: " + str(built.reason))
		return built
	var next: Node = built.game
	for id in humans:
		var admitted: Dictionary = next.add_player(id, humans[id], Vector2.ZERO, false, "", "user:" + humans[id])
		if not admitted.accepted:
			next.queue_free()
			push_error("Round handoff admission failed: " + str(admitted.reason))
			return admitted
	_install_shared_game(next, authority)
	if not humans.is_empty(): next.start_room_countdown()
	print("ROUND_HANDOFF=", JSON.stringify({"epoch": next.round_epoch, "humans": humans.keys(), "round": next.get_round_state()}))
	return {"accepted": true, "reason": "fresh_round", "epoch": next.round_epoch}

# Quick-start authenticates once. Active/results arrivals watch until next round,
# when humans take seats before the normal missing-seat bot admission runs.
func quick_start_game(peer_id: int, username: String) -> Dictionary:
	var prepared := _prepare_shared_game(_server_room_options)
	if not prepared.accepted: return prepared
	var game = active_games["shared_game"]
	for existing_name in _room_humans(game).values():
		if existing_name == username: return {"accepted": false, "reason": "participant_in_use"}
	var admission: Dictionary
	if game.match_active or not game.get_round_result().is_empty():
		admission = game.add_spectator(peer_id, username)
	else:
		admission = game.add_player(peer_id, username, Vector2.ZERO, false, "", "user:" + username)
	if not admission.accepted:
		print("[Server] Player admission refused: ", admission.reason)
		return admission
	if not game.match_active and game.get_round_result().is_empty() and game.get_room_capacity().configured:
		var started: Dictionary = game.start_room_countdown()
		if not started.accepted and started.reason != "content_not_ready":
			game.remove_player(peer_id)
			return started
	player_to_game[peer_id] = "shared_game"
	print("[Server] Player ", peer_id, " joined shared game.")
	return admission

func _prepare_content_offers(game: Node) -> Dictionary:
	_content_offer_template.clear()
	_content_archives.clear()
	if game.room_pack_paths.is_empty(): return {"accepted": true}
	var by_identity := {}
	var total_bytes := 0
	for path in game.room_pack_paths:
		var built := PackArchive.build(path)
		if not built.accepted: return built
		if not _content_archives.has(built.sha256):
			total_bytes += built.size_bytes
			if total_bytes > ContentDownload.MAX_SESSION_BYTES:
				return {"accepted": false, "reason": "content_session_byte_budget_exceeded", "field": "room_pack_paths", "source": ""}
		var identity: Dictionary = built.identity
		var key: String = identity.pack_id
		by_identity[key] = {"identity": identity.duplicate(true), "sha256": built.sha256, "size_bytes": built.size_bytes}
		_content_archives[built.sha256] = built.bytes
	var archives := []
	for identity in game.room_content_lock.packs:
		if not by_identity.has(identity.pack_id) or by_identity[identity.pack_id].identity != identity:
			return {"accepted": false, "reason": "content_archive_selection_mismatch", "field": "room_pack_paths", "source": ""}
		archives.append(by_identity[identity.pack_id])
	_content_offer_template = {"type": "offer", "session_id": "0".repeat(64), "lock": game.room_content_lock.duplicate(true),
		"lock_sha256": game.room_content_lock_sha256, "content_id": game.room_arena_id, "archives": archives}
	var checked := ContentDownload.validate_offer(_content_offer_template)
	if not checked.accepted: return checked
	return {"accepted": true}

func _begin_content(peer_id: int, username: String) -> void:
	var game = active_games["shared_game"]
	var capacity: Dictionary = game.get_room_capacity()
	if _pending_content.size() >= Constants.MAX_MATCH_SEATS or game.get_human_count() + _pending_content.size() >= capacity.seats:
		print("[Server] Player admission refused: room_full")
		get_node("/root/ClientMain").rpc_id(peer_id, "auth_response", {"success": false, "error": "room_full"})
		return
	var offer: Dictionary = _content_offer_template.duplicate(true)
	var random := Crypto.new().generate_random_bytes(32)
	if random.size() != 32:
		get_node("/root/ClientMain").rpc_id(peer_id, "auth_response", {"success": false, "error": "content_session_random_failed"})
		return
	offer.session_id = random.hex_encode()
	var held: Dictionary = game.set_content_waiting(peer_id, true)
	if not held.accepted:
		get_node("/root/ClientMain").rpc_id(peer_id, "auth_response", {"success": false, "error": held.reason})
		return
	_pending_content[peer_id] = {"username": username, "session_id": offer.session_id,
		"deadline": Time.get_ticks_msec() + ContentDownload.TIMEOUT_MSEC, "offsets": {}}
	get_node("/root/ClientMain").rpc_id(peer_id, "content_message", offer)
	print("[Server] Content offered before admission: ", peer_id)

func content_message(message: Dictionary) -> void:
	var peer_id := multiplayer.get_remote_sender_id()
	if not multiplayer.is_server() or peer_id <= 1 or not _pending_content.has(peer_id): return
	var pending: Dictionary = _pending_content[peer_id]
	if message.get("session_id") != pending.session_id:
		_fail_content(peer_id, "stale_content_session")
		return
	if Time.get_ticks_msec() >= pending.deadline:
		_fail_content(peer_id, "content_download_timeout")
		return
	match message.get("type"):
		"cancel":
			if not ContentDownload.exact_keys(message, ["type", "session_id"]):
				_fail_content(peer_id, "invalid_content_cancel")
			else:
				_fail_content(peer_id, "content_cancelled")
		"request":
			if not ContentDownload.exact_keys(message, ["type", "session_id", "sha256", "offset"]) or not message.get("sha256") is String or not _content_archives.has(message.sha256) or not message.get("offset") is int:
				_fail_content(peer_id, "invalid_content_request")
				return
			var bytes: PackedByteArray = _content_archives[message.sha256]
			var offset: int = message.offset
			if offset != pending.offsets.get(message.sha256, 0) or offset < 0 or offset >= bytes.size():
				_fail_content(peer_id, "unexpected_content_request_offset")
				return
			var end := mini(offset + ContentDownload.CHUNK_BYTES, bytes.size())
			pending.offsets[message.sha256] = end
			get_node("/root/ClientMain").rpc_id(peer_id, "content_message", {"type": "chunk", "session_id": pending.session_id,
				"sha256": message.sha256, "offset": offset, "data": bytes.slice(offset, end)})
		"ready":
			if not ContentDownload.exact_keys(message, ["type", "session_id", "lock_sha256"]) or message.get("lock_sha256") != _content_offer_template.lock_sha256:
				_fail_content(peer_id, "content_lock_mismatch")
				return
			for hash in pending.offsets:
				if pending.offsets[hash] != _content_archives[hash].size():
					_fail_content(peer_id, "content_transfer_incomplete")
					return
			var username: String = pending.username
			_clear_content_pending(peer_id, false)
			var admission := quick_start_game(peer_id, username)
			if admission.accepted:
				lobby_manager.add_player(peer_id, username)
				get_node("/root/ClientMain").rpc_id(peer_id, "auth_response", {"success": true, "username": username, "room": active_games["shared_game"].get_room_capacity()})
				print("[Server] Content ready; player admitted: ", peer_id)
			else:
				get_node("/root/ClientMain").rpc_id(peer_id, "auth_response", {"success": false, "error": admission.reason})
			_resume_content_room()
		_:
			_fail_content(peer_id, "invalid_content_message")

func _process(_delta: float) -> void:
	for peer_id in _pending_content.keys():
		if Time.get_ticks_msec() >= _pending_content[peer_id].deadline:
			_fail_content(peer_id, "content_download_timeout")

func _clear_content_pending(peer_id: int, resume: bool = true) -> void:
	if not _pending_content.has(peer_id): return
	_pending_content.erase(peer_id)
	if active_games.has("shared_game"):
		active_games["shared_game"].set_content_waiting(peer_id, false)
	if resume: _resume_content_room()

func _resume_content_room() -> void:
	if active_games.has("shared_game"):
		var game = active_games["shared_game"]
		if game.process_mode == Node.PROCESS_MODE_DISABLED:
			call_deferred("_clear_empty_shared_room", game)
		elif not game.match_active and game.get_round_result().is_empty() and not game.players.is_empty():
			game.start_room_countdown()

func _fail_content(peer_id: int, reason: String) -> void:
	if not _pending_content.has(peer_id): return
	var session_id: String = _pending_content[peer_id].session_id
	_clear_content_pending(peer_id)
	get_node("/root/ClientMain").rpc_id(peer_id, "content_message", {"type": "failure", "session_id": session_id, "reason": reason})
	get_node("/root/ClientMain").rpc_id(peer_id, "auth_response", {"success": false, "error": reason})

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
