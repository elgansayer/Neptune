extends Node2D

# Client-side game display with lag mitigation
# Implements Client-Side Prediction, Server Reconciliation, and Entity Interpolation
# Uses Godot's CanvasLayers, YSort, and z_index for proper rendering order

const Constants = preload("res://shared/constants.gd")
const CharacterPacks = preload("res://shared/content/character_pack_loader.gd")
const RenderingLayers = preload("res://shared/rendering_layers.gd")
const BombScene = preload("res://client/ui/bomb.tscn")
const PowerUpScene = preload("res://client/ui/powerup.tscn")
const GameHUDScene = preload("res://client/ui/game_hud.tscn")
const ThreatMatrixVisualizerScene = preload("res://client/ui/threat_matrix_visualizer.tscn")
const BombSafetyVisualizerScript = preload("res://client/ui/bomb_safety_visualizer.gd")
const HurryBlockShadowScene = preload("res://client/effects/HurryBlockShadow.tscn")
const FallingHurryBlockScene = preload("res://client/effects/FallingHurryBlock.tscn")
const ExplosionEventTimeline = preload("res://client/explosion_event_timeline.gd")

# Canvas layers (Godot feature for major separation)
var background_canvas: CanvasLayer
var game_canvas: CanvasLayer
var ui_canvas: CanvasLayer
var debug_canvas: CanvasLayer

# Containers within game canvas (Y-sorted for depth)
@onready var players_container = $Players
@onready var bombs_container = $Bombs
@onready var explosions_container = $Explosions
@onready var camera = $Camera2D

var player_nodes = {} # peer_id -> Node2D
var _local_character_visuals := {} # Explicit cosmetic selections; no network authority.
var bomb_nodes = {} # bomb_id -> Node2D
var powerup_nodes = {} # powerup_id -> Node2D
var egg_nodes = {} # egg_id -> Node2D (Tirra eggs)
var tirra_nodes = {} # tirra_id -> Node2D (hatched Tirra mounts)
var explosion_nodes = {} # explosion_id -> ExplosionRenderer
var _explosion_timeline := ExplosionEventTimeline.new()
var block_nodes = {} # tile_key -> Node2D (for destructible blocks)
var wall_nodes = {} # tile_key -> Node2D (for solid walls)
var hurry_block_nodes = {} # tile_key -> Node2D (for hurry mode blocks - landed)
var hurry_pending_shadows = {} # tile_key -> HurryBlockShadow (shadows before drop)
var hurry_falling_blocks = {} # tile_key -> FallingHurryBlock (blocks currently falling)
var debug_tiles = {} # tile_key -> ColorRect for debugging
var my_player_id = ""
var map_rendered = false
var arena_pixel_size := Vector2.ZERO
var render_geometry := false
var map_scene_instance = null # Hold reference to loaded PCK map scene
var removed_dead_players = {} # peer_id -> bool when death animation has finished and node was removed
var hud: CanvasLayer # Reference to HUD
var ai_debug_targets := {} # peer_id -> {"tile": Vector2i, "player_name": String}
var local_map := [] # Client-side copy of map state (updated via delta compression)

# Match state for win/lose animations
var match_winner_id := "" # ID of the winner (empty during gameplay, set when match ends)
var match_ended := false # True when match has ended

# Lag mitigation systems
var local_player_controller: ClientPlayerController # Prediction for local player
var remote_player_interpolators = {} # peer_id -> EntityInterpolator for remote players
var bomb_throw_predictor: BombThrowPredictor # Power Glove throw prediction

# AI threat matrix visualization (debug)
var threat_visualizer: Node2D = null
var bomb_safety_visualizer: Node2D = null

# Players rendered above HUD via dedicated CanvasLayer
var players_canvas: CanvasLayer = null

# Input buffering: track order of pressed keys
var input_buffer = [] # Array of currently pressed direction keys in order (most recent last)

# Timescale cycling
var current_timescale_index = 0
var timescale_options = [3.0, 5.0, 0.1, 0.25, 0.5, 1.0, 2.0]

# Cached server node reference to avoid repeated lookups
var server_node: Node = null

func _ready():
	# Cache server node reference
	server_node = get_node_or_null("/root/ServerMain")

	# Enable Y-sorting on game containers (Godot's built-in depth sorting)
	RenderingLayers.setup_ysort_container(self)  # Root game view
	RenderingLayers.setup_ysort_container(players_container)
	RenderingLayers.setup_ysort_container(bombs_container)
	RenderingLayers.setup_ysort_container(explosions_container)
	
	# Set up FIXED camera to show entire arena (like classic Bomberman)
	camera.enabled = true
	camera.anchor_mode = Camera2D.ANCHOR_MODE_DRAG_CENTER
	camera.position = Vector2.ZERO # Will be set when map loads
	camera.zoom = Vector2(1.0, 1.0) # Will be adjusted when map loads
	
	# Initialize prediction system for local player
	local_player_controller = ClientPlayerController.new()
	add_child(local_player_controller)
	
	# Initialize bomb throw predictor for Power Glove
	bomb_throw_predictor = BombThrowPredictor.new()
	add_child(bomb_throw_predictor)
	
	# Initialize threat matrix visualizer (debug - toggle with F3)
	threat_visualizer = ThreatMatrixVisualizerScene.instantiate()
	threat_visualizer.position = Vector2.ZERO # Explicitly set to (0, 0)
	add_child(threat_visualizer)
	print("[GameView] ThreatVisualizer created successfully at position: ", threat_visualizer.position)
	# Start with threat matrix hidden
	threat_visualizer.visible = false
	
	# Initialize bomb safety visualizer (debug - toggle with F4)
	bomb_safety_visualizer = BombSafetyVisualizerScript.new()
	bomb_safety_visualizer.name = "BombSafetyVisualizer"
	bomb_safety_visualizer.position = Vector2.ZERO
	add_child(bomb_safety_visualizer)
	print("[GameView] BombSafetyVisualizer created")
	# Start with bomb safety shown
	bomb_safety_visualizer.visible = true
	
	# Setup Godot CanvasLayers for proper rendering separation (after visualizers created)
	_setup_canvas_layers()
	
	# Request current safety data from server (in case we missed initial broadcasts)
	call_deferred("_request_farming_spot_update")

# Setup CanvasLayers using Godot's layering system
func _setup_canvas_layers() -> void:
	# Players canvas (must be ABOVE HUD/top bar)
	# This is the only reliable way to render players over UI in Godot.
	players_canvas = RenderingLayers.create_canvas_layer(
		RenderingLayers.CANVAS_PLAYERS,
		"PlayersCanvas"
	)
	players_canvas.follow_viewport_enabled = true
	players_canvas.follow_viewport_scale = 1.0
	get_tree().root.add_child(players_canvas)
	
	# Move player visuals into players canvas
	if players_container and players_container.get_parent():
		players_container.get_parent().remove_child(players_container)
		players_canvas.add_child(players_container)

	# Create debug canvas (overlays, paths, visualizers)
	debug_canvas = RenderingLayers.create_canvas_layer(
		RenderingLayers.CANVAS_DEBUG,
		"DebugCanvas"
	)
	get_tree().root.add_child(debug_canvas)
	
	# Move debug visualizers to debug canvas (remove from current parent first)
	if threat_visualizer and threat_visualizer.get_parent():
		threat_visualizer.get_parent().remove_child(threat_visualizer)
		debug_canvas.add_child(threat_visualizer)
	if bomb_safety_visualizer and bomb_safety_visualizer.get_parent():
		bomb_safety_visualizer.get_parent().remove_child(bomb_safety_visualizer)
		debug_canvas.add_child(bomb_safety_visualizer)
	
	print("[GameView] CanvasLayers configured: Game=%d Debug=%d" % [
		RenderingLayers.CANVAS_GAME,
		RenderingLayers.CANVAS_DEBUG
	])
	
	# Check for cached initial map data (might have arrived before we were ready)
	call_deferred("_check_pending_initial_map")

	# Start at normal speed
	Engine.time_scale = 1.0
	if server_node:
		server_node.rpc_id(1, "set_debug_timescale", 1.0)
	
	# Initialize HUD (must be above map but below players)
	hud = GameHUDScene.instantiate()
	hud.layer = RenderingLayers.CANVAS_UI
	# HUD must stay pinned to the screen
	hud.follow_viewport_enabled = false
	# HUD lives on CANVAS_UI; players are rendered on CANVAS_PLAYERS above it.
	add_child(hud)
	_connect_arena_framing()
	
	# Set player name in HUD once we know it
	if ClientMain.username:
		hud.set_player_name(ClientMain.username)
		
	# Connect latency signal
	if ClientMain.has_signal("latency_updated"):
		ClientMain.latency_updated.connect(_on_latency_updated)


func update_game_state(state: Dictionary):
	print("[GameView] State keys: ", state.keys())
	# Observe clock headers even without an event batch. This guard applies only
	# to presentation events; map/actor delta handling retains its existing flow.
	var accept_effect_snapshot := _explosion_timeline.observe_snapshot(
		state.get("simulation_tick"), state.get("server_time"), explosion_nodes)
	var explosion_events: Array = []
	if accept_effect_snapshot:
		if state.has("explosions"):
			if state.explosions is Array and state.explosions.size() <= ExplosionEventTimeline.MAX_SEEN_EVENTS:
				explosion_events = state.explosions
		elif state.has("e"):
			explosion_events = _explosion_timeline.decode_compact(state.e)
	# === COMPACT FORMAT CONVERSION ===
	# Server now sends compact keys to reduce packet size
	# Convert to legacy format for existing code compatibility
	if state.has("p") and not state.has("players"):
		# Compact player format - expand to legacy format
		state["players"] = {}
		for peer_id_str in state.p:
			var pmin = state.p[peer_id_str]
			# Expand minimal player state to full format for existing code
			# Keys: p=position, v=velocity, f=facing (U/D/L/R), d=dead, c=carried_bomb (optional)
			# Stats packed into 2 integers: s=[s1, s2]
			# s1: legacy stat nibbles; s2: bomb type and flags, including range high bit.
			# Virus state is transmitted separately.
			# flags = packed booleans (bit 0=kicker, 1=glove, 2=line_bomb, 3=carrying, 4=picking)
			
			var stats_packed = pmin.get("s", [0x1200, 0]) # Default: max_bombs=1, range=2
			var stats = preload("res://shared/player_snapshot_stats.gd").unpack(stats_packed)
			var max_bombs = stats.max_bombs
			var bomb_range = stats.bomb_range
			var bombs_placed = stats.bombs_placed
			var skate_count = stats.skate_count
			var bomb_type = stats.bomb_type
			var flags = stats.flags
			
			# Expand single-char facing back to full name
			var facing = "DOWN"
			var f = pmin.get("f", "D")
			if f == "U": facing = "UP"
			elif f == "D": facing = "DOWN"
			elif f == "L": facing = "LEFT"
			elif f == "R": facing = "RIGHT"
			else: facing = f # fallback to original if already full name
			
			var player_data = {
				"position": {"x": pmin.p[0], "y": pmin.p[1]},
				"velocity": {"x": pmin.v[0] if pmin.has("v") else 0, "y": pmin.v[1] if pmin.has("v") else 0},
				"facing": facing,
				"is_dead": pmin.get("d", false), # absent means alive
				"carried_bomb_id": pmin.get("c", null), # Optional - only present when carrying
				"is_panicking": pmin.get("k", false), # k = panicking (in danger)
				# Player stats from packed integers
				"max_bombs": max_bombs,
				"bomb_range": bomb_range,
				"bombs_placed": bombs_placed,
				"skate_count": skate_count,
				"speed_multiplier": 1.0 + (skate_count * 0.125), # Calculate from skate_count
				# Abilities from packed flags
				"has_bomb_kicker": (flags & 1) != 0,
				"has_power_glove": (flags & 2) != 0,
				"has_line_bomb": (flags & 4) != 0,
				"has_full_fire": (flags & 512) != 0,
				"is_carrying_bomb": (flags & 8) != 0,
				"is_picking_up_bomb": (flags & 16) != 0,
				"is_mounted": (flags & 32) != 0,  # Bit 5 = mounted on Tirra
				"is_flying": (flags & 64) != 0,   # Bit 6 = in arc jump
				"is_immortal": (flags & 128) != 0, # Bit 7 = invincible
				"flash_white": (flags & 256) != 0, # Bit 8 = white flash active
				# Bomb type and virus
				"bomb_type": bomb_type,
				"active_virus": pmin.get("av", 0),  # Active virus now separate field
				"virus_end_time": pmin.get("ve", 0.0),
				# Tirra mount data
				"tirra_growth_level": pmin.get("tl", 0),  # 0=BABY, 1=TEEN, 2=ADULT
			}
			# Optional pickup animation direction
			if pmin.has("pad"):
				player_data["pickup_animation_direction"] = {"x": pmin.pad[0], "y": pmin.pad[1]}
			state.players[peer_id_str] = player_data
	
	if state.has("b") and not state.has("bombs"):
		# Compact bomb format - expand to legacy format
		state["bombs"] = {}
		for bomb_id in state.b:
			var bmin = state.b[bomb_id]
			# Keys: p=position, t=timer, s=state, k=kick_direction (optional), z=z_height (optional)
			# Note: bomb_id is the dictionary key, not repeated inside
			var bomb_state = {
				"bomb_id": bomb_id, # Use the key as bomb_id
				"position": {"x": bmin.p[0], "y": bmin.p[1]},
				"timer": bmin.t / 100.0, # Convert centiseconds back to seconds
				"fuse_lower_bound": bmin.get("f", 300) / 100.0,
				"state": bmin.s,
			}
			if bmin.has("k"):
				bomb_state["kick_direction"] = {"x": bmin.k[0], "y": bmin.k[1]}
			if bmin.has("z"):
				bomb_state["z_height"] = bmin.z
			state.bombs[bomb_id] = bomb_state
	
	if state.has("pu") and not state.has("powerups"):
		# Compact powerup format - expand to legacy format
		# Server sends: pu_id -> [tile_x, tile_y, type]
		print("[GameView] Expanding ", state.pu.size(), " powerups")
		state["powerups"] = {}
		if state.pu is Dictionary:
			for pu_id in state.pu:
				var pu = state.pu[pu_id]
				# Convert tile coords to pixel coords (center of tile)
				var tile_size = GameConfig.TILE_SIZE
				state.powerups[pu_id] = {
					"powerup_id": pu_id,
					"position": {"x": pu[0] * tile_size + tile_size / 2, "y": pu[1] * tile_size + tile_size / 2},
					"type": pu[2]
				}
	
	# Expand compact egg format to usable format
	# Server sends: eg_id -> [tile_x, tile_y]
	if state.has("eg") and not state.has("eggs"):
		print("[GameView] Expanding ", state.eg.size(), " eggs")
		state["eggs"] = {}
		if state.eg is Dictionary:
			for eg_id in state.eg:
				var eg = state.eg[eg_id]
				var tile_size = GameConfig.TILE_SIZE
				state.eggs[eg_id] = {
					"egg_id": eg_id,
					"position": {"x": eg[0] * tile_size + tile_size / 2, "y": eg[1] * tile_size + tile_size / 2}
				}
	
	# Expand compact tirra format to usable format
	# Server sends: tr_id -> [pixel_x, pixel_y]
	if state.has("tr") and not state.has("tirras"):
		state["tirras"] = {}
		if state.tr is Dictionary:
			for tr_id in state.tr:
				var tr = state.tr[tr_id]
				state.tirras[tr_id] = {
					"tirra_id": tr_id,
					"position": {"x": tr[0], "y": tr[1]}
				}
	
	if state.has("t") and not state.has("match_timer"):
		state["match_timer"] = state.t
	if state.has("a") and not state.has("match_active"):
		state["match_active"] = state.a
	if state.has("c") and state.c != null and not state.has("countdown_time"):
		state["countdown_time"] = state.c
	if state.has("w") and state.w != null and not state.has("winner_id"):
		state["winner_id"] = state.w
	if state.has("h") and not state.has("hurry_mode_active"):
		state["hurry_mode_active"] = state.h
	if state.has("hb") and not state.has("hurry_blocks"):
		# Convert compact array format [x, y] to dict format {x, y}
		var expanded_blocks := []
		for hb in state.hb:
			if hb is Array and hb.size() >= 2:
				expanded_blocks.append({"x": hb[0], "y": hb[1]})
			else:
				expanded_blocks.append(hb) # Fallback for dict format
		state["hurry_blocks"] = expanded_blocks
	# === END COMPACT FORMAT CONVERSION ===
	
	# Load map_config first if present (must happen before rendering)
	if state.has("map_config") and not map_rendered:
		GameConfig.load_map_config(state.map_config)
		render_geometry = state.map_config.get("render_geometry", false)
		print("[GameView] Loaded map config: TILE_SIZE=", GameConfig.TILE_SIZE)
	
	# Handle packed map (compressed format for first sync)
	if not map_rendered and state.has("map_packed"):
		var packed = state.map_packed as PackedByteArray
		var width = state.get("map_width", 21)
		var height = state.get("map_height", 14)
		# Unpack into 2D array
		local_map = []
		var idx = 0
		for y in range(height):
			var row = []
			for x in range(width):
				if idx < packed.size():
					row.append(packed[idx])
					idx += 1
				else:
					row.append(0)
			local_map.append(row)
		render_map(local_map)
		update_blocks(local_map) # Populate soft blocks from server map data
		map_rendered = true
		
		print("[GameView] Map rendered from packed data, GameConfig.TILE_SIZE = ", GameConfig.TILE_SIZE)
		
		# Set map size for visualizers
		if threat_visualizer and threat_visualizer.has_method("set_map_size"):
			threat_visualizer.set_map_size(width, height)
		if bomb_safety_visualizer:
			bomb_safety_visualizer.set_map_size(width, height)
			bomb_safety_visualizer.update_tile_size(GameConfig.TILE_SIZE)
	
	# Handle full map (legacy format - fallback)
	if not map_rendered and state.has("map"):
		local_map = state.map.duplicate(true) # Deep copy
		render_map(state.map)
		update_blocks(local_map) # Populate soft blocks from server map data
		map_rendered = true
		
		print("[GameView] Map rendered, GameConfig.TILE_SIZE = ", GameConfig.TILE_SIZE)
		
		# Set map size for threat visualizer
		if threat_visualizer and threat_visualizer.has_method("set_map_size"):
			var map_height = state.map.size()
			var map_width = state.map[0].size()
			threat_visualizer.set_map_size(map_width, map_height)
		
		# Set map size for bomb safety visualizer
		if bomb_safety_visualizer:
			var map_height = state.map.size()
			var map_width = state.map[0].size()
			bomb_safety_visualizer.set_map_size(map_width, map_height)
			bomb_safety_visualizer.update_tile_size(GameConfig.TILE_SIZE)
	
	# Handle delta map changes (incremental updates) - now packed as [x, y, value] arrays
	if state.has("map_changes") and map_rendered:
		for change in state.map_changes:
			var x = change[0]
			var y = change[1]
			var value = change[2]
			if y >= 0 and y < local_map.size() and x >= 0 and x < local_map[y].size():
				local_map[y][x] = value
		# Apply changes to block visuals
		update_blocks(local_map)
	
	# Update destructible blocks based on full map state (if sent)
	if state.has("map"):
		local_map = state.map.duplicate(true) # Keep local copy in sync
		update_blocks(state.map)
	
	# Update threat matrix visualization (debug)
	if state.has("threat_matrix") and state.has("current_time_msec"):
		if threat_visualizer and is_instance_valid(threat_visualizer):
			# Check if the script has been fully initialized
			if threat_visualizer.has_method("update_threat_matrix"):
				threat_visualizer.update_threat_matrix(state.threat_matrix, state.current_time_msec)
		else:
			# Create visualizer on-demand if it doesn't exist yet
			if not threat_visualizer:
				threat_visualizer = ThreatMatrixVisualizerScene.instantiate()
				threat_visualizer.position = Vector2.ZERO
				add_child(threat_visualizer)
				# Keep default state hidden when created on-demand
				threat_visualizer.visible = false
				print("[GameView] ThreatVisualizer created on-demand")
				# Set map size if we have it
				if map_rendered and state.has("map") and state.map.size() > 0:
					var map_height = state.map.size()
					var map_width = state.map[0].size()
					if threat_visualizer.has_method("set_map_size"):
						threat_visualizer.set_map_size(map_width, map_height)
				# Now update with threat data
				if threat_visualizer.has_method("update_threat_matrix"):
					threat_visualizer.update_threat_matrix(state.threat_matrix, state.current_time_msec)
	
	# Update HUD timer and countdown
	if state.has("match_timer") and hud:
		hud.update_timer(state.match_timer)
	
	# Handle hurry mode
	if state.has("hurry_mode_active") and state.hurry_mode_active and hud:
		if hud.has_method("show_hurry_mode"):
			hud.show_hurry_mode()
	
	# Render hurry blocks
	if state.has("hurry_blocks"):
		_update_hurry_blocks(state.hurry_blocks)
	
	if state.has("countdown_time") and state.countdown_time > 0.0 and hud:
		hud.show_countdown(state.countdown_time)

	# Update player faces in HUD and count alive players
	if state.has("players") and hud:
		var alive_count = 0
		var participants: Dictionary = state.get("room", {}).get("participants", {})
		hud.update_player_roster(state.players, participants)
		for peer_id_str in state.players:
			var pdata = state.players[peer_id_str]
			var is_dead = pdata.get("is_dead", false)
			
			# Update face state based on player status
			if hud.has_method("update_player_face_state"):
				if is_dead:
					hud.update_player_face_state(peer_id_str, "lose")
				else:
					hud.update_player_face_state(peer_id_str, "idle")
					alive_count += 1
			else:
				if not is_dead:
					alive_count += 1
			
		
		hud.update_players_alive(alive_count, state.players.size())

	# Update players
	if state.has("players"):
		for peer_id_str in state.players:
			var player_data = state.players[peer_id_str]
			update_player(peer_id_str, player_data)

	# Update local player stats in HUD
	if state.has("players") and state.players.has(str(multiplayer.get_unique_id())) and hud:
		var my_data = state.players[str(multiplayer.get_unique_id())]
		hud.update_player_stats(
			my_data.get("bombs_placed", 0),
			my_data.get("max_bombs", 1),
			my_data.get("bomb_range", 2),
			my_data.get("speed_multiplier", 1.0)
		)
		
		# Update virus status in HUD
		if hud.has_method("update_virus_status"):
			var virus_type = my_data.get("active_virus", 0)
			var virus_end_time = my_data.get("virus_end_time", 0.0)
			var server_time = state.get("server_time", 0.0)
			var time_remaining = max(0.0, (virus_end_time - server_time) / 1000.0)
			if virus_type != 0:
				print("[GameView] Updating virus HUD: type=%d time=%.1f" % [virus_type, time_remaining])
			hud.update_virus_status(virus_type, time_remaining)
		else:
			print("[GameView] WARNING: hud.update_virus_status not found!")
		
		# Check if local player became a spectator (eliminated)
		if my_data.get("is_spectator", false) and hud.has_method("show_spectator_mode"):
			hud.show_spectator_mode()

	# Check for game over
	# IMPORTANT: match_active=false during countdown AND after game ends
	# Only show game over if countdown is complete (countdown_time <= 0)
	var countdown_complete = not state.has("countdown_time") or state.countdown_time <= 0.0
	var has_match_ended = state.has("match_active") and not state.match_active and countdown_complete
	
	# Update class-level match state for animations
	if has_match_ended:
		match_ended = true
		if state.has("winner_id") and state.winner_id:
			match_winner_id = state.winner_id
	
	if has_match_ended and hud:
		var winner_name = ""
		if state.has("winner_id") and state.winner_id:
			if state.has("players") and state.players.has(state.winner_id):
				winner_name = state.players[state.winner_id].get("username", "Unknown")
		hud.show_game_over(winner_name)

	# Remove players no longer in state
	if state.has("players"):
		for peer_id in _local_character_visuals.keys():
			if not state.players.has(peer_id): _local_character_visuals.erase(peer_id)
		for peer_id in player_nodes.keys():
			if not state.players.has(peer_id):
				player_nodes[peer_id].queue_free()
				player_nodes.erase(peer_id)

	# Update bombs
	if state.has("bombs"):
		for bomb_id in state.bombs:
			var bomb_data = state.bombs[bomb_id]
			update_bomb(bomb_id, bomb_data)

	# Remove bombs no longer in state
	if state.has("bombs"):
		for bomb_id in bomb_nodes.keys():
			if not state.bombs.has(bomb_id):
				bomb_nodes[bomb_id].queue_free()
				bomb_nodes.erase(bomb_id)

	# Update power-ups
	if state.has("powerups"):
		for powerup_id in state.powerups:
			var powerup_data = state.powerups[powerup_id]
			update_powerup(powerup_id, powerup_data)
		
		# Remove power-ups no longer in state
		for powerup_id in powerup_nodes.keys():
			if not state.powerups.has(powerup_id):
				powerup_nodes[powerup_id].queue_free()
				powerup_nodes.erase(powerup_id)

	# Update eggs (Tirra eggs)
	if state.has("eggs"):
		print("[GameView] Processing ", state.eggs.size(), " eggs")
		for egg_id in state.eggs:
			var egg_data = state.eggs[egg_id]
			update_egg(egg_id, egg_data)
		
		# Remove eggs no longer in state
		for egg_id in egg_nodes.keys():
			if not state.eggs.has(egg_id):
				egg_nodes[egg_id].queue_free()
				egg_nodes.erase(egg_id)

	# Update tirras (hatched mounts waiting to be picked up)
	if state.has("tirras"):
		for tirra_id in state.tirras:
			var tirra_data = state.tirras[tirra_id]
			update_tirra(tirra_id, tirra_data)
		
		# Remove tirras no longer in state
		for tirra_id in tirra_nodes.keys():
			if not state.tirras.has(tirra_id):
				tirra_nodes[tirra_id].queue_free()
				tirra_nodes.erase(tirra_id)

	# These are additive event batches, not a complete active-effect roster.
	if accept_effect_snapshot:
		update_explosions(explosion_events)

func _on_latency_updated(latency_ms: int):
	if hud and hud.has_method("update_latency"):
		hud.update_latency(latency_ms)

func update_ai_debug(debug_data: Dictionary) -> void:
	# Extract target cell from AI debug payload and forward to visualizer
	if debug_data.is_empty() or not debug_data.has("peer_id"):
		return

	var peer_id = str(debug_data.peer_id)
	var target_value = debug_data.get("target_cell", null)
	var normalized_tile = _normalize_tile(target_value)

	if normalized_tile == null:
		ai_debug_targets.erase(peer_id)
	else:
		ai_debug_targets[peer_id] = {
			"tile": normalized_tile,
			"player_name": debug_data.get("player_name", "Bot %s" % peer_id)
		}

	if threat_visualizer and threat_visualizer.has_method("update_target_tiles"):
		threat_visualizer.update_target_tiles(ai_debug_targets)

func _normalize_tile(value):
	if value == null:
		return null
	if value is Vector2i:
		return value
	if value is Vector2:
		return Vector2i(int(value.x), int(value.y))
	if typeof(value) == TYPE_DICTIONARY and value.has("x") and value.has("y"):
		return Vector2i(int(value.x), int(value.y))

func update_blocks(map_data: Array):
	"""Update destructible blocks based on current server map state"""
	
	# If we have the PCK map loaded, update the SpawnAndSoftBlockMap directly
	if map_scene_instance != null:
		var spawn_soft_map = map_scene_instance.get_node_or_null("SpawnAndSoftBlockMap")
		if spawn_soft_map:
			# Clear all soft block tiles first
			for cell in spawn_soft_map.get_used_cells():
				var source_id = spawn_soft_map.get_cell_source_id(cell)
				if source_id == 0: # Soft blocks (source 0)
					spawn_soft_map.erase_cell(cell)
			
			# Add soft blocks based on server map state
			for row in range(map_data.size()):
				for col in range(map_data[row].size()):
					if map_data[row][col] == 2: # Soft block exists
						# Set tile at this position (source 0, atlas coords (0,0))
						spawn_soft_map.set_cell(Vector2i(col, row), 0, Vector2i(0, 0))
			
			return # Done - TileMap handles rendering
	
	# Fallback: use ColorRect rendering
	var current_blocks = {}
	
	# Check which blocks should exist
	for row in range(map_data.size()):
		for col in range(map_data[row].size()):
			var tile_type = map_data[row][col]
			var tile_key = "%d,%d" % [col, row]
			
			if tile_type == 2: # Destructible block
				current_blocks[tile_key] = true
				
				# Create block if it doesn't exist
				if not block_nodes.has(tile_key):
					var block = ColorRect.new()
					block.color = Color(0.6, 0.5, 0.4)
					block.size = Vector2(GameConfig.TILE_SIZE, GameConfig.TILE_SIZE)
					block.position = Vector2(col * GameConfig.TILE_SIZE, row * GameConfig.TILE_SIZE)
					block.z_index = 0
					add_child(block)
					
					# Hitbox visualization removed
					
					block_nodes[tile_key] = {"block": block}
	
	# Remove blocks that no longer exist (destroyed)
	for tile_key in block_nodes.keys():
		if not current_blocks.has(tile_key):
			print("[Client] Removing destroyed block: ", tile_key)
			var nodes = block_nodes[tile_key]
			nodes.block.queue_free()
			block_nodes.erase(tile_key)

func select_local_character(peer_id: String, manifest_paths: Array, content_id: String) -> Dictionary:
	if RegEx.create_from_string("^-?[0-9]{1,12}\\z").search(peer_id) == null:
		return {"accepted": false, "reason": "invalid_participant_id"}
	if player_nodes.has(peer_id):
		return {"accepted": false, "reason": "visual_already_created"}
	var loaded := CharacterPacks.load_character(manifest_paths, content_id)
	if not loaded.accepted: return loaded
	_local_character_visuals[peer_id] = loaded
	return {"accepted": true, "descriptor": loaded.descriptor.duplicate(true)}

func update_player(peer_id: String, data: Dictionary):
	var player_node

	if not data.has("is_dead") or not data.is_dead:
		removed_dead_players.erase(peer_id)
	
	if not player_nodes.has(peer_id):
		if data.has("is_dead") and data.is_dead and removed_dead_players.get(peer_id, false):
			return
		# Create new player visual
		player_node = Node2D.new()
		player_node.name = "Player_" + peer_id
		
		var sprite_root: Node2D = null
		var fallback := "state_idle"
		if _local_character_visuals.has(peer_id):
			var selected: Dictionary = _local_character_visuals[peer_id]
			sprite_root = CharacterPacks.create_visual(selected)
			fallback = selected.fallback
			player_node.set_meta("character_descriptor", selected.descriptor.duplicate(true))
		else:
			# Preserve the existing default visual when no local choice was made.
			var player_pck_scene = load("res://player.tscn")
			if player_pck_scene: sprite_root = player_pck_scene.instantiate()
		if sprite_root:
			sprite_root.position = Vector2.ZERO
			player_node.add_child(sprite_root)
			# Store reference to AnimatedSprite2D for animation control
			var anim_sprite = sprite_root.get_node_or_null("AnimatedSprite2D")
			if anim_sprite:
				anim_sprite.play(fallback)
				player_node.set_meta("animated_sprite", anim_sprite)
				player_node.set_meta("character_fallback", fallback)
		else:
			# Fallback to colored rectangle if PCK not loaded
			var sprite = ColorRect.new()
			var sprite_size = GameConfig.TILE_SIZE / 2.0 # Half tile size
			sprite.size = Vector2(sprite_size, sprite_size)
			sprite.position = Vector2(-sprite_size / 2, -sprite_size / 2)
			var is_local = str(peer_id) == str(multiplayer.get_unique_id())
			sprite.color = Color(0.2, 0.6, 1.0) if is_local else Color(1.0, 0.3, 0.3)
			player_node.add_child(sprite)
		
		# Debug arrow removed
		
		# Label removed for better visibility
		# var label = Label.new()
		# label.text = data.username
		# var label_offset = GameConfig.TILE_SIZE * 0.625  # Proportional offset (40px at 64px tiles)
		# label.position = Vector2(-label_offset / 2, -label_offset)
		# player_node.add_child(label)
		
		# Add raycast visualization line
		var raycast_debug_line = Line2D.new()
		# Width = collision shape diameter to show actual raycast width
		raycast_debug_line.width = GameConfig.PLAYER_HALF_WIDTH * 2.0 # Dynamic diameter
		raycast_debug_line.default_color = Color(0, 1, 1, 1.0) # Cyan
		raycast_debug_line.z_index = 100 # Fixed: within valid range
		raycast_debug_line.antialiased = true
		raycast_debug_line.name = "RaycastLine"
		player_node.add_child(raycast_debug_line)
		
		# Add ShapeCast2D visualization (showing the collision check shape)
		var shapecast_visual = Line2D.new()
		shapecast_visual.width = GameConfig.PLAYER_HALF_WIDTH * 2.0 # Same size as player
		shapecast_visual.default_color = Color(1, 0, 0, 0.6) # Red by default
		shapecast_visual.z_index = 101
		shapecast_visual.antialiased = true
		shapecast_visual.name = "ShapeCastVisual"
		player_node.add_child(shapecast_visual)

		# Add target-centering debug line (player center to target tile center)
		var target_debug_line = Line2D.new()
		target_debug_line.width = 3.0
		target_debug_line.default_color = Color(1, 0, 0, 0.9)
		target_debug_line.antialiased = true
		target_debug_line.z_index = 150
		target_debug_line.name = "TargetDebugLine"
		player_node.add_child(target_debug_line)
		
		players_container.add_child(player_node)
		player_nodes[peer_id] = player_node
		
		# If this is our player, follow with camera and initialize prediction
		if peer_id == str(multiplayer.get_unique_id()):
			my_player_id = peer_id
			# Initialize prediction with spawn position
			local_player_controller.reset_prediction(Vector2(data.position.x, data.position.y))
		else:
			# Create interpolator for remote players
			var interpolator = EntityInterpolator.new()
			remote_player_interpolators[peer_id] = interpolator
			add_child(interpolator)
	else:
		player_node = player_nodes[peer_id]
	
	# Don't update position if player is dead (handled in animation section below)
	if data.has("is_dead") and data.is_dead:
		# Still need to process animations for death, so continue
		pass
	else:
		var target_pos = Vector2(data.position.x, data.position.y)
		var target_vel = Vector2(data.velocity.x, data.velocity.y)
		
		# Apply lag mitigation based on player type
		if peer_id == my_player_id:
			# LOCAL PLAYER: Direct server position (no interpolation)
			local_player_controller.reconcile_with_server(data)
			# Use server position directly - feels like the original working version
			player_node.position = local_player_controller.predicted_position
		else:
			# REMOTE PLAYER: Entity Interpolation
			if remote_player_interpolators.has(peer_id):
				var interpolator = remote_player_interpolators[peer_id]
				interpolator.add_server_state(target_pos, target_vel)
				player_node.position = interpolator.get_interpolated_position()
			else:
				# Fallback: direct update
				player_node.position = target_pos

			# When the server says the bot is effectively stationary, snap to its exact position
			if target_vel.length() < 0.5:
				player_node.position = target_pos

	_update_target_debug_line(player_node, data)
	
	# Debug arrow removed
	
	# Update Robin Hood animations based on state and movement
	var animated_sprite = player_node.get_meta("animated_sprite", null)
	if animated_sprite:
		# Check if player is dead
		var is_player_dead = data.has("is_dead") and data.is_dead
		
		# Handle death animation and removal
		if is_player_dead:
			# Ensure we only start the death animation once
			if not player_node.get_meta("death_anim_started", false):
				player_node.set_meta("death_anim_started", true)
				print("[GameView] Player ", peer_id, " killed - playing death animation")
				
				# Flash red when hit by bomb
				_play_death_flash(animated_sprite)
				
				if animated_sprite.sprite_frames.has_animation("state_defeat"):
					animated_sprite.play("state_defeat")
				else:
					animated_sprite.visible = false
					_remove_dead_player(peer_id)
					return
				
			if not player_node.get_meta("death_anim_cleanup_connected", false):
				var cleanup_callable := func(finished_anim: StringName = &""):
					if finished_anim != &"" and finished_anim != "state_defeat":
						return
					_remove_dead_player(peer_id)
				player_node.set_meta("death_anim_cleanup_connected", true)
				animated_sprite.animation_finished.connect(cleanup_callable, Object.CONNECT_ONE_SHOT)
			
			# Don't update position/animations during death beyond this point
			return
		
		# Get direction prefix from facing data
		var direction_prefix = "down" # Default
		if data.has("facing"):
			match data.facing:
				"RIGHT":
					direction_prefix = "right"
				"DOWN":
					direction_prefix = "down"
				"LEFT":
					direction_prefix = "left"
				"UP":
					direction_prefix = "up"
		
		# Store last direction for when player stops
		player_node.set_meta("last_direction", direction_prefix)
		
		# Determine animation based on state priority
		var anim_name = ""
		var velocity = Vector2(data.velocity.x, data.velocity.y)
		var is_moving = velocity.length() >= 10.0
		var is_mounted = data.get("is_mounted", false)
		var is_flying = data.get("is_flying", false)
		
		# Priority 0: Match ended - Winner/Loser animations (highest priority after death)
		if match_ended:
			if match_winner_id == peer_id:
				# This player won - play celebration!
				anim_name = "state_win"
			elif match_winner_id != "":
				# Match has a winner but it's not this player - play lose animation
				anim_name = "state_lose"
			# If winner_id is empty, it's a draw - keep normal animations
		# Priority 1: Stunned state
		elif data.has("is_stunned") and data.is_stunned:
			anim_name = "state_stunned"
		# Priority 2: Panic state (near explosion)
		elif data.has("is_panicking") and data.is_panicking:
			anim_name = "state_panic"
		# Priority 3: Picking up bomb (animation)
		elif data.has("is_picking_up_bomb") and data.is_picking_up_bomb:
			# Get pickup animation direction
			var pickup_dir = "down" # Default
			if data.has("pickup_animation_direction"):
				var pickup_vec = Vector2(data.pickup_animation_direction.x, data.pickup_animation_direction.y)
				if abs(pickup_vec.y) > abs(pickup_vec.x):
					pickup_dir = "up" if pickup_vec.y < 0 else "down"
				else:
					pickup_dir = "left" if pickup_vec.x < 0 else "right"
			anim_name = pickup_dir + "_pglove_pickup"
		# Priority 4: Carrying bomb
		elif data.has("is_carrying_bomb") and data.is_carrying_bomb:
			if is_moving:
				anim_name = direction_prefix + "_carry"
			else:
				anim_name = direction_prefix + "_hold"
		# Priority 5: Flying/Arc jump (mounting/dismounting Tirra)
		elif is_flying:
			anim_name = direction_prefix + "_jump"
		# Priority 6: Mounted on Tirra - player shows ride animation
		elif is_mounted:
			anim_name = direction_prefix + "_ride"
			# Update Tirra visual if it exists
			_update_tirra_visual(player_node, data, direction_prefix, is_moving)
		# Priority 7: Walking
		elif is_moving:
			anim_name = direction_prefix + "_walk"
		# Priority 8: Stopped (directional idle)
		else:
			anim_name = direction_prefix + "_stopped"
		
		# Handle Tirra visual (create/remove as needed)
		_manage_tirra_visual(player_node, is_mounted, data)
		
		# Play animation if it changed (with safety check)
		# Also restart non-looping state animations if they've finished
		var should_play: bool = animated_sprite.animation != anim_name
		if not should_play and anim_name.begins_with("state_") and not animated_sprite.is_playing():
			# State animations may not loop - restart them if they've stopped
			should_play = true
		
		if should_play:
			if animated_sprite.sprite_frames.has_animation(anim_name):
				animated_sprite.play(anim_name)
			else:
				var fallback: String = player_node.get_meta("character_fallback", "state_idle")
				print("[GameView] Animation not found: ", anim_name, " - using ", fallback)
				if animated_sprite.sprite_frames.has_animation(fallback):
					animated_sprite.play(fallback)
	
	# === VIRUS VISUAL EFFECTS (Saturn Bomberman) ===
	_update_virus_visual_effects(player_node, data)
	
	# === IMMORTALITY FLASH EFFECT (Saturn Bomberman) ===
	# When player is invincible (after Tirra hit), they flash white
	_update_immortality_flash(player_node, data)
	
	# === FLYING/ARC JUMP VISUAL (Saturn Bomberman) ===
	# Scale effect when player is in mid-air during arc jump
	_update_flying_visual(player_node, data)
	
	# Debug visualization removed - only direction arrow remains
	# (debug_blocking_tile, debug_check_tile, raycast lines removed for clean gameplay)
	
# DEBUG_DISABLED: 	# Update raycast line based on last_move_direction
# DEBUG_DISABLED: 	var raycast_line = player_node.get_node_or_null("RaycastLine")
# DEBUG_DISABLED: 	if raycast_line and data.has("last_move_direction"):
# DEBUG_DISABLED: 		var last_move = Vector2(data.last_move_direction.x, data.last_move_direction.y)
# DEBUG_DISABLED: 		if last_move.length() > 0.1:
# DEBUG_DISABLED: 			raycast_line.clear_points()
# DEBUG_DISABLED: 			raycast_line.add_point(Vector2.ZERO)
# DEBUG_DISABLED: 			raycast_line.add_point(motion)
# DEBUG_DISABLED: 		else:
# DEBUG_DISABLED: 			raycast_line.clear_points()
# DEBUG_DISABLED: 	
# DEBUG_DISABLED: 	# Update ShapeCast2D visual if we have shape_cast data
# DEBUG_DISABLED: 	var shapecast_visual = player_node.get_node_or_null("ShapeCastVisual")
# DEBUG_DISABLED: 	if shapecast_visual and data.has("shape_cast_target"):
# DEBUG_DISABLED: 		var target = Vector2(data.shape_cast_target.x, data.shape_cast_target.y)
# DEBUG_DISABLED: 		var is_colliding = data.get("shape_cast_colliding", false)
# DEBUG_DISABLED: 		
# DEBUG_DISABLED: 		# Update color based on collision state
# DEBUG_DISABLED: 		shapecast_visual.default_color = Color(1, 0, 0, 0.6) if is_colliding else Color(0, 1, 0, 0.4)
# DEBUG_DISABLED: 		
# DEBUG_DISABLED: 		# Draw the shape cast line
# DEBUG_DISABLED: 		if target.length() > 0.1:
# DEBUG_DISABLED: 			shapecast_visual.clear_points()
# DEBUG_DISABLED: 			shapecast_visual.add_point(Vector2.ZERO)
# DEBUG_DISABLED: 			shapecast_visual.add_point(target)
# DEBUG_DISABLED: 		else:
# DEBUG_DISABLED: 			shapecast_visual.clear_points()
	
	# Camera is FIXED - don't follow player (classic Bomberman style)
	# Commented out: camera should show entire arena at all times
	# if peer_id == my_player_id:
	# 	camera.position = player_node.position


## Tirra Visual Management Functions
## These manage the visual representation of Tirra mounts on the client side

func _manage_tirra_visual(player_node: Node2D, is_mounted: bool, data: Dictionary) -> void:
	"""Create or remove Tirra visual based on mounted state."""
	var tirra_visual = player_node.get_node_or_null("TirraVisual")
	var player_sprite = player_node.get_node_or_null("AnimatedSprite2D")
	
	if is_mounted:
		if not tirra_visual:
			# Load the actual Tirra scene from PCK
			var tirra_scene = load("res://tirra.tscn")
			if tirra_scene:
				tirra_visual = tirra_scene.instantiate()
				tirra_visual.name = "TirraVisual"
				tirra_visual.z_index = 0  # Render at same level (below player sprite which gets z_index 1)
				tirra_visual.position = Vector2.ZERO  # Center on player
				
				# Set growth level if the Tirra controller supports it
				var growth_level = data.get("tirra_growth_level", 0)
				if tirra_visual.has_method("set_growth_level"):
					tirra_visual.set_growth_level(growth_level)
				elif "current_level" in tirra_visual:
					tirra_visual.current_level = growth_level
				
				player_node.add_child(tirra_visual)
				
				# Ensure player sprite renders above Tirra
				if player_sprite:
					player_sprite.z_index = 1
				
				# Debug: Print children to verify the structure
				print("[GameView] Created Tirra visual, growth_level=", growth_level)
				for child in tirra_visual.get_children():
					if child is AnimatedSprite2D:
						print("  - ", child.name, " visible=", child.visible)
				
				print("[GameView] Created Tirra visual for mounted player, tirra z=0, player sprite z=1")
			else:
				# Fallback: Create a simple placeholder
				tirra_visual = Sprite2D.new()
				tirra_visual.name = "TirraVisual"
				tirra_visual.z_index = 0
				# Create a placeholder colored rect
				var placeholder = ColorRect.new()
				placeholder.color = Color(0.3, 0.6, 1.0, 0.8)  # Blue
				placeholder.size = Vector2(14, 14)
				placeholder.position = Vector2(-7, -7)
				tirra_visual.add_child(placeholder)
				player_node.add_child(tirra_visual)
				push_warning("[GameView] Could not load tirra.tscn, using placeholder")
		else:
			# Tirra visual already exists, update growth level if changed
			var growth_level = data.get("tirra_growth_level", 0)
			if tirra_visual.has_method("set_growth_level"):
				tirra_visual.set_growth_level(growth_level)
			elif "current_level" in tirra_visual:
				var old_level = tirra_visual.get("current_level")
				if old_level != growth_level:
					tirra_visual.current_level = growth_level
	else:
		# Remove Tirra visual when dismounted
		if tirra_visual:
			tirra_visual.queue_free()
		
		# Reset player sprite position and z_index when not mounted
		if player_sprite:
			player_sprite.position = Vector2.ZERO
			player_sprite.z_index = 0
			player_sprite.z_as_relative = true  # Reset to default


func _update_tirra_visual(player_node: Node2D, data: Dictionary, player_direction: String, is_moving: bool) -> void:
	"""Update Tirra animation and apply rider offset."""
	var tirra_visual = player_node.get_node_or_null("TirraVisual")
	if not tirra_visual:
		return
	
	# Convert player direction to Tirra direction format
	var tirra_direction = _player_dir_to_tirra_dir(player_direction)
	
	# Determine Tirra animation
	var tirra_anim = ""
	if is_moving:
		tirra_anim = tirra_direction + "_walk"
	else:
		tirra_anim = tirra_direction + "_stopped"
	
	# The Tirra scene has a controller script that manages child sprites (baby/teen/adult)
	# We need to find the active sprite and play the animation on it
	var growth_level = data.get("tirra_growth_level", 0)

	# First ensure the controller's current_level is set correctly
	# The controller's _update_visibility() will handle showing/hiding the right sprite
	if tirra_visual.has_method("set_growth_level"):
		tirra_visual.set_growth_level(growth_level)
	elif "current_level" in tirra_visual:
		if tirra_visual.get("current_level") != growth_level:
			tirra_visual.current_level = growth_level
	
	# Get the currently active sprite from the controller's _current_sprite
	var tirra_sprite: AnimatedSprite2D = null
	if "_current_sprite" in tirra_visual:
		tirra_sprite = tirra_visual.get("_current_sprite")
	
	# Fallback: manually find the visible sprite if controller doesn't expose _current_sprite
	if not tirra_sprite:
		for child in tirra_visual.get_children():
			if child is AnimatedSprite2D:
				if child.visible:
					tirra_sprite = child
					break
	
	# Debug: Check if sprite has frames
	if tirra_sprite and tirra_sprite.sprite_frames:
		if tirra_sprite.sprite_frames.get_frame_count("default") == 0 and tirra_sprite.sprite_frames.get_frame_count("idle") == 0:
			print("[GameView] WARNING: Tirra sprite '", tirra_sprite.name, "' has no frames in 'default' or 'idle' animation!")
		
		if not tirra_sprite:
			# Debug: check what children exist
			print("[GameView] No visible Tirra sprite found. Growth level: ", growth_level)
			print("[GameView] Tirra children: ", tirra_visual.get_children().map(func(c): return c.name + " (visible=" + str(c.visible) + ")" if c is AnimatedSprite2D else c.name))
	
	if tirra_sprite:
		# Play animation if valid - with fallback for missing/empty animations
		# Some Tirra directions (up, left, right) may have empty frame lists
		var anim_to_play = tirra_anim
		if tirra_sprite.sprite_frames:
			# Check if requested animation exists and has frames
			var has_valid_anim = tirra_sprite.sprite_frames.has_animation(tirra_anim) and \
				tirra_sprite.sprite_frames.get_frame_count(tirra_anim) > 0
			
			if not has_valid_anim:
				# Fallback to down direction (which always has frames)
				if is_moving:
					anim_to_play = "down_walk"
				else:
					anim_to_play = "down_stopped"
				# Final check - make sure fallback exists
				if not tirra_sprite.sprite_frames.has_animation(anim_to_play) or \
					tirra_sprite.sprite_frames.get_frame_count(anim_to_play) == 0:
					anim_to_play = "idle"  # Last resort fallback
			
			if tirra_sprite.animation != anim_to_play:
				tirra_sprite.play(anim_to_play)
		
		# Z-index changes based on direction for proper layering:
		# - Looking up (away from camera): Player renders in front of Tirra
		# - Looking down (toward camera): Tirra renders in front of player
		# Set on the actual tirra sprite, not parent container
		var tirra_z_table = {
			"up": 1,    # Tirra behind player (player walking away)
			"down": 2,   # Tirra in front (player walking toward camera)
			"left": 1,  # Tirra behind
			"right": 1, # Tirra behind
		}
		tirra_sprite.z_index = tirra_z_table.get(tirra_direction, 1)
		tirra_sprite.z_as_relative = true  # Use relative z-index
		
		# Ensure the parent container (TirraVisual) doesn't interfere with z-index
		tirra_visual.z_index = 0
		tirra_visual.z_as_relative = true
	else:
		push_warning("[GameView] Tirra sprite not found for growth level: " + str(growth_level))
	
	# Apply rider offset based on direction and growth level
	var rider_offset = _get_tirra_rider_offset(growth_level, tirra_direction)
	
	# The player sprite needs to be offset when mounted
	var player_sprite = player_node.get_node_or_null("AnimatedSprite2D")
	if not player_sprite:
		# Try to find it in the sprite_root if it's nested
		for child in player_node.get_children():
			if child.name != "TirraVisual" and child is Node2D:
				player_sprite = child.get_node_or_null("AnimatedSprite2D")
				if player_sprite:
					# Also ensure the player's sprite parent doesn't interfere
					child.z_index = 0
					child.z_as_relative = true
					break

	if player_sprite:
		player_sprite.position = rider_offset
		
		# Player z-index opposite to tirra for proper layering
		var player_z_table = {
			"up": 2,     # Player in front (walking away)
			"down": 1,  # Player behind (walking toward camera)
			"left": 2,   # Player in front
			"right": 2,  # Player in front
		}
		player_sprite.z_index = player_z_table.get(tirra_direction, 2)
		player_sprite.z_as_relative = true  # Use relative z-index


func _player_dir_to_tirra_dir(player_dir: String) -> String:
	"""Return Tirra direction name (up/down/left/right)."""
	match player_dir:
		"up", "down", "left", "right":
			return player_dir
		_:
			return "down"


func _get_tirra_rider_offset(growth_level: int, direction: String = "down") -> Vector2:
	"""Get the rider offset for a Tirra based on growth level and direction.
	
	Offsets from original SBomberman:
	- Baby: Y=-20, X=13 for left, X=-13 for right
	- Teen: Y=-25, X=13 for left, X=-13 for right  
	- Adult: Y=-45, X=13 for left, X=-13 for right
	"""
	# Comprehensive offset table: [growth_level][direction] = Vector2(x, y)
	# Growth levels: 0=BABY, 1=TEEN, 2=ADULT
	# Directions: up, down, left, right
	const RIDER_OFFSETS = {
		0: {  # BABY (Small Tirra)
			"up":    Vector2(0.0, -8.5),
			"down":  Vector2(0.0, -8.5),
			"left":  Vector2(5.5, -8.5),
			"right": Vector2(-5.5, -8.5)
		},
		1: {  # TEEN (Medium Tirra)
			"up":    Vector2(0.0, -10.5),
			"down":  Vector2(0.0, -10.5),
			"left":  Vector2(6.5, -10.5),
			"right": Vector2(-6.5, -10.5)
		},
		2: {  # ADULT (Large Tirra)
			"up":    Vector2(0.0, -12.5),
			"down":  Vector2(0.0, -12.5),
			"left":  Vector2(5.5, -12.5),
			"right": Vector2(-5.5, -12.5),
		}
	}
	
	# Lookup with fallback to default
	if RIDER_OFFSETS.has(growth_level) and RIDER_OFFSETS[growth_level].has(direction):
		return RIDER_OFFSETS[growth_level][direction]
	else:
		push_warning("[GameView] Unknown Tirra offset: level=%d, dir=%s" % [growth_level, direction])
		return Vector2(0.0, -6.0)  # Safe fallback


func _get_tirra_sprite_frames(growth_level: int) -> SpriteFrames:
	"""Load Tirra sprite frames from PCK based on growth level."""
	# Tirra PCK structure: res://tirra_animations.tres or similar
	# Try several common paths where Tirra resources might be
	var possible_paths = [
		"res://tirra_animations.tres",
		"res://tirra/animations.tres",
		"res://tirra_sprite_frames.tres",
		"res://characters/tirra_animations.tres"
	]
	
	for path in possible_paths:
		if ResourceLoader.exists(path):
			var frames = ResourceLoader.load(path) as SpriteFrames
			if frames:
				return frames
	
	# Fallback: Try to create basic sprite frames from texture
	var texture_paths = [
		"res://tirra_sheet.png",
		"res://tirra/tirra.png",
		"res://characters/tirra.png"
	]
	
	for path in texture_paths:
		if ResourceLoader.exists(path):
			# Found texture, but we'd need proper SpriteFrames setup
			# For now return null and handle gracefully
			push_warning("Found Tirra texture at %s but no SpriteFrames. Need proper animation setup." % path)
			break
	
	return null


func update_bomb(bomb_id: String, data: Dictionary):
	var bomb_node
	
	if not bomb_nodes.has(bomb_id):
		# Create new bomb visual with SBomberman animations
		bomb_node = BombScene.instantiate()
		bomb_node.bomb_id = bomb_id
		bomb_node.name = "Bomb_" + bomb_id
		bomb_node.z_index = RenderingLayers.BOMBS # Render bombs using RenderingLayers system
		
		bombs_container.add_child(bomb_node)
		bomb_nodes[bomb_id] = bomb_node
		
		# Play plant sound on first appearance
		bomb_node.plant_bomb()
	else:
		bomb_node = bomb_nodes[bomb_id]
	
	# Update position and timer
	bomb_node.position = Vector2(data.position.x, data.position.y)
	bomb_node.update_timer(data.timer)
	
	# Handle visibility (for out-of-bounds during wrap-around)
	if data.has("is_visible"):
		bomb_node.visible = data.is_visible
	else:
		bomb_node.visible = true # Default to visible
	
	# Handle Power Glove states
	if data.has("state"):
		var bomb_state = data.state
		bomb_node.set_bomb_state(bomb_state)
		
		# Update Z-height for thrown bombs (server handles CARRIED positioning already)
		if bomb_state == BombRenderer.BombState.THROWN and data.has("z_height"):
			bomb_node.update_z_height(data.z_height)
		else:
			bomb_node.update_z_height(0.0) # Reset Z height for other states

func update_explosions(explosions_data: Array):
	"""Accept delivered events once; each renderer owns its visual lifetime."""
	for explosion_data in explosions_data:
		var event: Dictionary = _explosion_timeline.accept_event(explosion_data, explosion_nodes)
		if not event.accepted:
			continue
		var explosion_id: String = event.bomb_id
		var explosion_node := ExplosionRenderer.new()
		explosion_node.explosion_id = explosion_id
		explosion_node.name = "Explosion_%d" % explosion_node.get_instance_id()
		explosion_node.z_index = RenderingLayers.EXPLOSIONS
		explosion_nodes[explosion_id] = explosion_node
		explosion_node.tree_exiting.connect(_on_explosion_tree_exiting.bind(explosion_id, explosion_node.get_instance_id()), Object.CONNECT_ONE_SHOT)
		# Immediate late-event sampling needs ready child sprites.
		explosions_container.add_child(explosion_node)
		explosion_node.initialize(event.pattern, event.start_time, _explosion_timeline.server_time_msec / 1000.0)
		# Preserve the existing linked-bomb dispatch, now guarded by event identity.
		# This does not fix a missing bomb link or establish sample-accurate audio.
		if bomb_nodes.has(explosion_id):
			var linked_bomb = bomb_nodes[explosion_id]
			if is_instance_valid(linked_bomb) and linked_bomb.has_method("explode"):
				linked_bomb.explode()


func _on_explosion_tree_exiting(explosion_id: String, instance_id: int) -> void:
	var current = explosion_nodes.get(explosion_id)
	if not is_instance_valid(current) or current.get_instance_id() == instance_id:
		explosion_nodes.erase(explosion_id)


func reset_explosion_timeline() -> void:
	# Explicit view/room lifecycle boundary only. A decreasing network clock is
	# never sufficient evidence of a new room or replay epoch.
	for node in explosion_nodes.values():
		if is_instance_valid(node):
			node.set_physics_process(false)
			node.queue_free()
	explosion_nodes.clear()
	_explosion_timeline.reset()

func _expand_explosion_pattern(explosion_data: Dictionary) -> Array:
	"""Convert direction counts pattern to enriched tile data for ExplosionRenderer
	Input: {center: {x, y}, pattern: {up: n, down: n, left: n, right: n}}
	Output: [{grid_pos: {x, y}, length: n, direction: str, is_end: bool}, ...]"""
	var tiles := []
	var center_x = explosion_data["center"]["x"]
	var center_y = explosion_data["center"]["y"]
	var pattern = explosion_data["pattern"]
	
	# Center tile
	tiles.append({
		"grid_pos": {"x": center_x, "y": center_y},
		"length": 0,
		"direction": "middle",
		"is_end": false
	})
	
	# Direction vectors and names
	var directions = {
		"up": Vector2i(0, -1),
		"down": Vector2i(0, 1),
		"left": Vector2i(-1, 0),
		"right": Vector2i(1, 0)
	}
	
	for dir_name in directions:
		var dir_vec = directions[dir_name]
		var count = pattern.get(dir_name, 0)
		
		for i in range(1, count + 1):
			var pos_x = center_x + dir_vec.x * i
			var pos_y = center_y + dir_vec.y * i
			var is_end = (i == count)
			
			# Determine sprite direction (horizontal or vertical)
			var sprite_dir = "horizontal" if dir_name in ["left", "right"] else "vertical"
			
			tiles.append({
				"grid_pos": {"x": pos_x, "y": pos_y},
				"length": i,
				"direction": sprite_dir,
				"is_end": is_end
			})
	
	return tiles

func _update_target_debug_line(player_node: Node2D, data: Dictionary) -> void:
	var target_line := player_node.get_node_or_null("TargetDebugLine")
	if not target_line:
		return

	if not data.get("debug_has_target", false) or not data.has("debug_target_center"):
		target_line.clear_points()
		target_line.visible = false
		return

	var center_dict: Dictionary = data.debug_target_center
	var target_center = Vector2(center_dict.get("x", 0.0), center_dict.get("y", 0.0))
	var offset = target_center - player_node.position
	
	target_line.visible = true
	target_line.clear_points()
	target_line.add_point(Vector2.ZERO)
	target_line.add_point(offset)

func _physics_process(delta):
	# Update input buffer based on which keys are pressed
	var directions = ["ui_up", "ui_down", "ui_left", "ui_right"]
	
	# Check for newly pressed keys
	for dir in directions:
		if Input.is_action_just_pressed(dir):
			# Remove if already in buffer (shouldn't happen but just in case)
			if dir in input_buffer:
				input_buffer.erase(dir)
			# Add to end of buffer (most recent)
			input_buffer.append(dir)
	
	# Check for released keys
	for dir in directions:
		if Input.is_action_just_released(dir):
			input_buffer.erase(dir)
	
	# Get the most recent direction that's still pressed
	var input_x = 0.0
	var input_y = 0.0
	
	if input_buffer.size() > 0:
		var current_dir = input_buffer[input_buffer.size() - 1] # Last element = most recent
		match current_dir:
			"ui_right":
				input_x = 1.0
			"ui_left":
				input_x = -1.0
			"ui_down":
				input_y = 1.0
			"ui_up":
				input_y = -1.0
	
	var place_bomb = Input.is_action_just_pressed("place_bomb")
	var action_pressed = Input.is_action_just_pressed("player_action")
	var action_released = Input.is_action_just_released("player_action")
	
	# Separate controls:
	# - Space (place_bomb): Place bombs, pickup/throw with Power Glove
	# - Shift/E (player_action): Kick action (Tirra kick, etc.)
	# The server will determine the appropriate action based on player state
	
	# SIMPLIFIED APPROACH: Just use server state with smooth interpolation
	# Prediction is too complex to match server's corner sliding + grid snapping
	var input_dir = Vector2(input_x, input_y)
	if my_player_id != "" and player_nodes.has(my_player_id):
		# Keep prediction state updated but don't use it for visuals
		var _predicted_state = local_player_controller.predict_movement(input_dir, delta, [])
		# Visual position comes from server via reconciliation in update_player
	
	# Send input to server (server remains authoritative)
	if server_node:
		server_node.rpc_id(1, "send_player_input", {
			"input_x": input_x,
			"input_y": input_y,
			"place_bomb": place_bomb,
			"action_pressed": action_pressed,
			"action_released": action_released
		})

func _play_death_flash(sprite: Node2D):
	"""Turn the player red when hit by a bomb explosion"""
	if not is_instance_valid(sprite):
		return
	
	# Turn red and stay red during death animation
	sprite.modulate = Color(1.0, 0.2, 0.2, 1.0)

func _remove_dead_player(peer_id: String):
	if player_nodes.has(peer_id):
		var node = player_nodes[peer_id]
		if is_instance_valid(node):
			node.queue_free()
		player_nodes.erase(peer_id)
	if remote_player_interpolators.has(peer_id):
		remote_player_interpolators[peer_id].queue_free()
		remote_player_interpolators.erase(peer_id)
	if peer_id == my_player_id:
		my_player_id = ""
	removed_dead_players[peer_id] = true

func _input(event):
	# Toggle debug visualizers with F3/F4
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == Key.KEY_F3:
			if threat_visualizer:
				threat_visualizer.visible = not threat_visualizer.visible
				print("[GameView] Threat visualizer: ", "ON" if threat_visualizer.visible else "OFF")
		elif event.keycode == Key.KEY_F4:
			if bomb_safety_visualizer:
				bomb_safety_visualizer.visible = not bomb_safety_visualizer.visible
				print("[GameView] Bomb safety visualizer: ", "ON" if bomb_safety_visualizer.visible else "OFF")
		elif event.keycode == Key.KEY_F5:
			current_timescale_index = (current_timescale_index + 1) % timescale_options.size()
			var new_timescale = timescale_options[current_timescale_index]
			Engine.time_scale = new_timescale
			if server_node:
				server_node.rpc_id(1, "set_debug_timescale", new_timescale)
			print("[GameView] Timescale set to: ", new_timescale)

		elif event.keycode == Key.KEY_F7:
			# Toggle timing display on threat visualizer
			if threat_visualizer and threat_visualizer.has_method("toggle_timing"):
				threat_visualizer.show_timing = not threat_visualizer.show_timing
				print("[GameView] Threat timing: ", "ON" if threat_visualizer.show_timing else "OFF")
		elif event.keycode == Key.KEY_F8:
			# Request test farming spot search from server
			print("[GameView] Requesting test farming spot search (F8)")
			_request_farming_spot_update()

func _request_farming_spot_update() -> void:
	"""Request the server to broadcast current farming spot evaluation"""
	if multiplayer.has_multiplayer_peer():
		ServerMain.rpc_id(1, "test_farming_spot_broadcast")

func _check_pending_initial_map() -> void:
	"""Check if ClientMain has cached initial map data that arrived before we were ready"""
	var client_main = get_tree().root.get_node_or_null("ClientMain")
	if client_main and client_main.has_method("get_pending_initial_map"):
		var pending_map = client_main.get_pending_initial_map()
		if not pending_map.is_empty():
			print("[GameView] Applying cached initial map data")
			update_game_state(pending_map)

func render_map(map_data):
	# Get map dimensions
	var map_height = map_data.size()
	var map_width = map_data[0].size() if map_height > 0 else 0
	
	# Try to load the map from PCK first
	var pck_path = "res://maps/stage1.pck"
	var pck_loaded = false
	
	if not render_geometry and FileAccess.file_exists(pck_path):
		var success = ProjectSettings.load_resource_pack(pck_path)
		if success:
			print("[GameView] Mounted PCK: ", pck_path)
			
			# Try to load Stage.tscn from PCK
			var scene_path = ""
			for potential_path in ["res://Stage.tscn", "res://Map.tscn", "res://stage.tscn"]:
				if ResourceLoader.exists(potential_path):
					scene_path = potential_path
					break
			
			if scene_path != "":
				var map_scene_res = load(scene_path)
				if map_scene_res != null:
					map_scene_instance = map_scene_res.instantiate()
					
					# Get TileMap layers
					var wall_floor_map = map_scene_instance.get_node_or_null("WallAndFloorBlockMap")
					var spawn_soft_map = map_scene_instance.get_node_or_null("SpawnAndSoftBlockMap")
					
					# WallAndFloorBlockMap stays HIDDEN - we use physics collision, not visual tiles
					# Floor and hard walls are handled by server physics
					if wall_floor_map:
						wall_floor_map.visible = false # Keep hidden
						# wall_floor_map.scale = Vector2(4.0, 4.0)
					
					# SpawnAndSoftBlockMap: Initially hide all soft blocks - server will sync actual positions
					if spawn_soft_map:
						spawn_soft_map.visible = true # Make visible (we'll control individual tiles)
						
						# Remove ALL tiles from SpawnAndSoftBlockMap
						# The server will tell us which soft blocks actually exist via map data
						# This prevents showing the pre-designed pattern before server sync
						var all_cells = spawn_soft_map.get_used_cells()
						print("[GameView] Clearing ", all_cells.size(), " tiles from SpawnAndSoftBlockMap (waiting for server)")
						for cell in all_cells:
							spawn_soft_map.erase_cell(cell)
					
					# Add map scene to game view
					add_child(map_scene_instance)
					map_scene_instance.z_index = -1
					
					print("[GameView] Loaded map from PCK: ", scene_path)
					pck_loaded = true
	
	# Fallback to ColorRect rendering if PCK not loaded
	if not pck_loaded:
		print("[GameView] PCK not found, using placeholder rendering")
		
		# Draw background for the play area - sized to actual map
		var bg = ColorRect.new()
		bg.color = Color(0.15, 0.25, 0.15) # Dark green background
		bg.size = Vector2(GameConfig.TILE_SIZE * map_width, GameConfig.TILE_SIZE * map_height)
		bg.position = Vector2.ZERO # Start from top-left
		bg.z_index = -1
		add_child(bg)
		
		# Render tiles based on map data
		# 0 = empty, 1 = wall (indestructible), 2 = destructible block
		for row in range(map_data.size()):
			for col in range(map_data[row].size()):
				var tile_type = map_data[row][col]
				
				if tile_type == 1:
					# Indestructible wall - dark gray
					var wall = ColorRect.new()
					wall.color = Color(0.3, 0.3, 0.35)
					wall.size = Vector2(GameConfig.TILE_SIZE, GameConfig.TILE_SIZE)
					wall.position = Vector2(col * GameConfig.TILE_SIZE, row * GameConfig.TILE_SIZE)
					wall.z_index = 0
					add_child(wall)
					
				elif tile_type == 2:
					# Destructible block - lighter brown/tan
					var block = ColorRect.new()
					block.color = Color(0.6, 0.5, 0.4)
					block.size = Vector2(GameConfig.TILE_SIZE, GameConfig.TILE_SIZE)
					block.position = Vector2(col * GameConfig.TILE_SIZE, row * GameConfig.TILE_SIZE)
					block.z_index = 0
					add_child(block)
					block_nodes["%d,%d" % [col, row]] = {"block": block}
					
					
					# Hitbox visualization removed
	
	arena_pixel_size = Vector2(map_width, map_height) * GameConfig.TILE_SIZE
	_update_arena_framing()

func _connect_arena_framing() -> void:
	get_viewport().size_changed.connect(_update_arena_framing)
	hud.arena_inset_changed.connect(_update_arena_framing)

func _update_arena_framing() -> void:
	if arena_pixel_size == Vector2.ZERO or not is_instance_valid(camera): return
	var top_inset: float = hud.get_node("TopBar").offset_bottom if is_instance_valid(hud) else 24.0
	var layout: Dictionary = preload("res://client/arena_framing.gd").fit(arena_pixel_size, get_viewport().get_visible_rect().size, top_inset)
	if not layout.accepted: return # A minimized/zero-size viewport cannot be framed yet.
	camera.position = layout.position
	camera.zoom = layout.zoom

func show_debug_tile(tile_pos: Vector2i, color: Color):
	"""Show a colored overlay on a tile for debugging"""
	var tile_key = "%d,%d" % [tile_pos.x, tile_pos.y]
	
	# Remove old debug tile if exists
	if debug_tiles.has(tile_key):
		debug_tiles[tile_key].queue_free()
		debug_tiles.erase(tile_key)
	
	# Create new debug overlay
	var debug_rect = ColorRect.new()
	debug_rect.size = Vector2(GameConfig.TILE_SIZE, GameConfig.TILE_SIZE)
	debug_rect.color = color
	debug_rect.position = Vector2(
		tile_pos.x * GameConfig.TILE_SIZE,
		tile_pos.y * GameConfig.TILE_SIZE
	)
	debug_rect.z_index = 100 # On top of everything
	
	# Add to scene
	add_child(debug_rect)
	debug_tiles[tile_key] = debug_rect
	
	# Auto-remove after a short time
	await get_tree().create_timer(0.15).timeout
	if is_instance_valid(debug_rect):
		debug_rect.queue_free()
	if debug_tiles.has(tile_key):
		debug_tiles.erase(tile_key)

# Receive bomb safety evaluation data from server (called locally by ClientMain)
func bomb_safety_update(safety_data: Dictionary) -> void:
	"""Update bomb safety visualizer with server's tile evaluations"""
	print("[GameView] bomb_safety_update received with %d tiles" % safety_data.size())
	if bomb_safety_visualizer and bomb_safety_visualizer.has_method("update_safety_data"):
		bomb_safety_visualizer.update_safety_data(safety_data)
	else:
		print("[GameView] WARNING: bomb_safety_visualizer not ready or missing method")

func update_powerup(powerup_id: String, data: Dictionary):
	print("[GameView] update_powerup called: id=", powerup_id, " type=", data.type, " pos=", data.position)
	var powerup_node
	
	if not powerup_nodes.has(powerup_id):
		# Create new power-up visual with SBomberman animations
		powerup_node = PowerUpScene.instantiate()
		powerup_node.powerup_id = powerup_id
		powerup_node.name = "PowerUp_" + powerup_id
		powerup_node.position = Vector2(data.position.x, data.position.y)
		powerup_node.powerup_type = data.type
		add_child(powerup_node)
		
		# Set powerup type and start animation
		powerup_node.set_powerup_type(data.type)
		powerup_nodes[powerup_id] = powerup_node
	else:
		powerup_node = powerup_nodes[powerup_id]
		# Update position (shouldn't change, but just in case)
		powerup_node.position = Vector2(data.position.x, data.position.y)

func update_egg(egg_id: String, data: Dictionary):
	"""Update or create a Tirra egg visual on the client side"""
	print("[GameView] update_egg called: id=", egg_id, " pos=", data.position)
	var egg_node
	
	if not egg_nodes.has(egg_id):
		# Try to load egg scene
		print("[GameView] Loading egg scene for id=", egg_id)
		var egg_scene = load("res://items/egg.tscn")
		if not egg_scene:
			print("[GameView] ERROR: Could not load egg.tscn, using fallback")
			# Fallback: create a simple placeholder sprite
			egg_node = Sprite2D.new()
			egg_node.texture = load("res://res/icons/egg.png") if FileAccess.file_exists("res://res/icons/egg.png") else null
			if egg_node.texture == null:
				# Create a simple colored rectangle as last resort
				var placeholder = ColorRect.new()
				placeholder.color = Color(1.0, 0.9, 0.7)  # Cream color for egg
				placeholder.size = Vector2(12, 16)
				placeholder.position = Vector2(-6, -8)  # Center it
				egg_node = Node2D.new()
				egg_node.add_child(placeholder)
		else:
			print("[GameView] Egg scene loaded, instantiating...")
			egg_node = egg_scene.instantiate()
			print("[GameView] Egg instantiated: ", egg_node.name, " visible=", egg_node.visible)
			# Disable server-side functionality (physics, pickup detection)
			# The egg is just a visual on the client - the server handles pickup
			var pickup_area = egg_node.get_node_or_null("PickupArea")
			if pickup_area:
				pickup_area.set_deferred("monitoring", false)
		
		egg_node.name = "Egg_" + egg_id
		egg_node.position = Vector2(data.position.x, data.position.y)
		egg_node.z_index = RenderingLayers.ITEMS  # Render below players via RenderingLayers system
		print("[GameView] Adding egg to scene: pos=", egg_node.position, " z_index=", egg_node.z_index)
		add_child(egg_node)
		print("[GameView] Egg added! Parent=", egg_node.get_parent().name, " in_tree=", egg_node.is_inside_tree())
		
		# CRITICAL FIX: Egg scene has AnimatedSprite2D visible=false by default
		# The spawn animation sets it to visible, but we need to force it on the client
		var sprite = egg_node.get_node_or_null("AnimatedSprite2D")
		if sprite:
			sprite.visible = true
			print("[GameView] Egg sprite DETAIL: visible=", sprite.visible, " scale=", sprite.scale, " modulate=", sprite.modulate, " z_index=", sprite.z_index, " position=", sprite.position)
			print("[GameView] Egg sprite animation=", sprite.animation, " frame=", sprite.frame, " playing=", sprite.playing)
		else:
			print("[GameView] ERROR: AnimatedSprite2D not found in egg!")
		
		print("[GameView] Egg node FINAL: visible=", egg_node.visible, " z_index=", egg_node.z_index, " scale=", egg_node.scale, " modulate=", egg_node.modulate)
		print("[GameView] Egg global_pos=", egg_node.global_position, " local_pos=", egg_node.position)
		
		egg_nodes[egg_id] = egg_node
	else:
		egg_node = egg_nodes[egg_id]
		# Update position (shouldn't change, but just in case)
		egg_node.position = Vector2(data.position.x, data.position.y)

func update_tirra(tirra_id: String, data: Dictionary):
	"""Update or create a Tirra mount visual on the client side"""
	var tirra_node
	
	if not tirra_nodes.has(tirra_id):
		# Try to load Tirra scene from PCK
		var tirra_scene = load("res://tirra.tscn")
		if not tirra_scene:
			# Fallback: create a simple placeholder sprite
			var placeholder = ColorRect.new()
			placeholder.color = Color(0.3, 0.6, 1.0)  # Blue color for Tirra
			placeholder.size = Vector2(14, 14)
			placeholder.position = Vector2(-7, -7)  # Center it
			tirra_node = Node2D.new()
			tirra_node.add_child(placeholder)
		else:
			tirra_node = tirra_scene.instantiate()
			# Disable server-side functionality (physics, pickup detection)
			# The tirra is just a visual on the client - the server handles pickup
			var pickup_area = tirra_node.get_node_or_null("PickupArea")
			if pickup_area:
				pickup_area.set_deferred("monitoring", false)
		
		tirra_node.name = "Tirra_" + tirra_id
		tirra_node.position = Vector2(data.position.x, data.position.y)
		add_child(tirra_node)
		tirra_nodes[tirra_id] = tirra_node
	else:
		tirra_node = tirra_nodes[tirra_id]
		# Update position (tirra might move or bounce)
		tirra_node.position = Vector2(data.position.x, data.position.y)

func _update_hurry_blocks(hurry_blocks_data: Array):
	"""Update hurry mode blocks on the client side"""
	# Track which blocks currently exist to detect new ones
	var new_blocks := {}
	
	for block_data in hurry_blocks_data:
		var tile_x: int = block_data.x if block_data is Dictionary else block_data["x"]
		var tile_y: int = block_data.y if block_data is Dictionary else block_data["y"]
		var tile_key = "%d,%d" % [tile_x, tile_y]
		new_blocks[tile_key] = true
		
		# Only create if doesn't exist yet (and not already pending/falling)
		if not hurry_block_nodes.has(tile_key) and not hurry_pending_shadows.has(tile_key) and not hurry_falling_blocks.has(tile_key):
			_spawn_hurry_block_with_warning(tile_x, tile_y, tile_key)
	
	# No need to remove hurry blocks - they stay until game ends

func _spawn_hurry_block_with_warning(tile_x: int, tile_y: int, tile_key: String):
	"""SNES Super Bomberman 2 authentic hurry block spawn:
	   1. Shadow appears for 60 frames (1 second) with pulse animation
	   2. Block spawns 256 pixels above target and falls at 12 px/frame
	   3. Block snaps to grid on impact, camera shakes, z-index changes"""
	
	var target_tile = Vector2i(tile_x, tile_y)
	
	# Step 1: Create the shadow from scene
	var shadow = HurryBlockShadowScene.instantiate()
	shadow.set_target_tile(target_tile)
	add_child(shadow)
	hurry_pending_shadows[tile_key] = shadow
	
	# Step 2: When shadow warning completes, spawn the falling block
	shadow.shadow_warning_complete.connect(func():
		_spawn_falling_hurry_block(tile_x, tile_y, tile_key, shadow)
	)

func _spawn_falling_hurry_block(tile_x: int, tile_y: int, tile_key: String, shadow: Node2D):
	"""Spawn the falling block after shadow warning completes"""
	var target_tile = Vector2i(tile_x, tile_y)
	
	# Create the falling block from scene
	var falling_block = FallingHurryBlockScene.instantiate()
	falling_block.setup(target_tile, shadow)
	add_child(falling_block)
	hurry_falling_blocks[tile_key] = falling_block
	
	# Connect to landing signal
	falling_block.block_landed.connect(func(tile: Vector2i):
		_on_hurry_block_landed(tile_key, tile, falling_block, shadow)
	)
	
	# Start the fall
	falling_block.start_falling()

func _on_hurry_block_landed(tile_key: String, tile: Vector2i, falling_block: Node2D, shadow: Node2D):
	"""Handle hurry block landing - screen shake, cleanup, add to landed blocks"""
	
	# Camera shake effect (SNES-authentic "thud")
	_shake_camera_on_impact()
	
	# Move falling block reference to landed blocks
	hurry_block_nodes[tile_key] = falling_block
	hurry_falling_blocks.erase(tile_key)
	
	# Clean up shadow
	if shadow and is_instance_valid(shadow):
		hurry_pending_shadows.erase(tile_key)
		shadow.cleanup()
	
	print("[GameView] Hurry block LANDED at (%d, %d)" % [tile.x, tile.y])

func _shake_camera_on_impact():
	"""Screen shake effect when hurry block lands - SNES-authentic feel"""
	if not camera:
		return
	
	var original_offset = camera.offset
	var shake_intensity = 1.0 * GameConfig.scale_factor # Subtle shake
	var shake_duration = 0.15 # Quick shake
	
	var tween = create_tween()
	# Rapid oscillation
	tween.tween_property(camera, "offset", original_offset + Vector2(shake_intensity, 0), 0.02)
	tween.tween_property(camera, "offset", original_offset + Vector2(-shake_intensity, shake_intensity * 0.5), 0.02)
	tween.tween_property(camera, "offset", original_offset + Vector2(shake_intensity * 0.5, -shake_intensity * 0.5), 0.02)
	tween.tween_property(camera, "offset", original_offset + Vector2(-shake_intensity * 0.3, shake_intensity * 0.3), 0.02)
	tween.tween_property(camera, "offset", original_offset, 0.07)

# Legacy function kept for compatibility - redirects to new system
func _create_hurry_block_visual(tile_x: int, tile_y: int, tile_key: String):
	"""Legacy wrapper - now uses SNES-authentic shadow + falling block system"""
	_spawn_hurry_block_with_warning(tile_x, tile_y, tile_key)

# === SATURN BOMBERMAN VIRUS VISUAL EFFECTS ===
# Infected players flash black and have a skull icon floating above them

func _update_virus_visual_effects(player_node: Node2D, data: Dictionary) -> void:
	"""Update virus visual effects (flashing + skull icon) based on server state"""
	var has_virus = data.has("active_virus") and data.active_virus != 0
	var virus_end_time = data.get("virus_end_time", 0.0)
	
	# Get or create skull icon
	var skull_icon = player_node.get_node_or_null("VirusSkullIcon")
	if has_virus:
		if not skull_icon:
			skull_icon = _create_skull_icon()
			skull_icon.name = "VirusSkullIcon"
			player_node.add_child(skull_icon)
		
		# Animate skull bobbing
		var time = Time.get_ticks_msec() / 1000.0
		skull_icon.position.y = - GameConfig.TILE_SIZE * 1.2 + sin(time * 6.0) * 3.0
		skull_icon.visible = true
	elif skull_icon:
		skull_icon.visible = false
	
	# Get the animated sprite for flashing effect
	var animated_sprite = player_node.get_meta("animated_sprite", null)
	if animated_sprite:
		var peer_id = str(data.get("peer_id", ""))
		if has_virus:
			# Flash black at 5Hz (Saturn Bomberman style)
			var time_ms = Time.get_ticks_msec()
			var flash_cycle = int(time_ms / 100) % 2 # Toggle every 100ms (5Hz)
			var flash_color: Color
			if flash_cycle == 0:
				flash_color = Color(0.1, 0.1, 0.1) # Nearly black
			else:
				flash_color = Color.WHITE # Normal
			animated_sprite.modulate = flash_color
			# Sync HUD avatar flash
			if hud and peer_id:
				hud.update_player_face_modulate(peer_id, flash_color)
		else:
			# Ensure modulate is reset when virus clears
			if animated_sprite.modulate != Color.WHITE:
				animated_sprite.modulate = Color.WHITE
				# Sync HUD avatar reset
				if hud and peer_id:
					hud.update_player_face_modulate(peer_id, Color.WHITE)

func _create_skull_icon() -> Node2D:
	"""Create a floating skull icon for infected players"""
	var skull_container = Node2D.new()
	skull_container.z_index = 200 # Above player
	
	# Create skull using simple shapes (or load texture if available)
	var skull = Label.new()
	skull.text = "☠" # Unicode skull emoji
	skull.add_theme_font_size_override("font_size", int(GameConfig.TILE_SIZE * 0.5))
	skull.add_theme_color_override("font_color", Color(0.8, 0.1, 0.8)) # Purple
	skull.add_theme_color_override("font_outline_color", Color.BLACK)
	skull.add_theme_constant_override("outline_size", 2)
	skull.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	skull.position = Vector2(-skull.size.x / 2, 0)
	
	skull_container.add_child(skull)
	return skull_container

# === SATURN BOMBERMAN IMMORTALITY FLASH EFFECT ===
# When player is invincible (after Tirra dies), they flash bright white

func _update_immortality_flash(player_node: Node2D, data: Dictionary) -> void:
	"""Update immortality flash effect (Saturn Bomberman style invincibility frames)"""
	var is_immortal = data.get("is_immortal", false)
	var flash_white = data.get("flash_white", false)
	
	# Get the animated sprite for flashing effect
	var animated_sprite = player_node.get_meta("animated_sprite", null)
	if not animated_sprite:
		return
	
	# Store last immortal state to detect transitions
	var was_immortal = player_node.get_meta("was_immortal", false)
	player_node.set_meta("was_immortal", is_immortal)
	
	var peer_id = str(data.get("peer_id", ""))
	if is_immortal:
		# Flash between bright white and normal (Saturn Bomberman style)
		# Note: This overrides virus flash when both active (immortal takes priority)
		var flash_color: Color
		if flash_white:
			# Bright white flash - make sprite glow
			flash_color = Color(2.5, 2.5, 2.5, 1.0)
		else:
			flash_color = Color.WHITE
		animated_sprite.modulate = flash_color
		# Sync HUD avatar flash
		if hud and peer_id:
			hud.update_player_face_modulate(peer_id, flash_color)
	elif was_immortal and not is_immortal:
		# Immortality just ended - ensure modulate is restored
		# Only restore if no virus is active
		var has_virus = data.has("active_virus") and data.active_virus != 0
		if not has_virus:
			animated_sprite.modulate = Color.WHITE
			# Sync HUD avatar reset
			if hud and peer_id:
				hud.update_player_face_modulate(peer_id, Color.WHITE)

# === SATURN BOMBERMAN ARC JUMP/FLYING VISUAL ===
# When player is in mid-air during arc jump (mounting/dismounting Tirra)

func _update_flying_visual(player_node: Node2D, data: Dictionary) -> void:
	"""Update flying visual effect (arc jump during Tirra mount/dismount)"""
	var is_flying = data.get("is_flying", false)
	
	# Get the sprite container for scale effect
	var animated_sprite = player_node.get_meta("animated_sprite", null)
	if not animated_sprite:
		return
	
	# Store last flying state to detect transitions
	var was_flying = player_node.get_meta("was_flying", false)
	player_node.set_meta("was_flying", is_flying)
	
	if is_flying:
		# Slight scale increase to indicate height + shadow could be added
		animated_sprite.scale = Vector2(1.15, 1.15)
		# Could also add a simple drop shadow here
	elif was_flying and not is_flying:
		# Landing - restore normal scale
		animated_sprite.scale = Vector2.ONE
