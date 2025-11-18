extends Node2D

# Client-side game display with lag mitigation
# Implements Client-Side Prediction, Server Reconciliation, and Entity Interpolation

const Constants = preload("res://shared/constants.gd")
const BombScene = preload("res://client/ui/bomb.tscn")
const PowerUpScene = preload("res://client/ui/powerup.tscn")
const GameHUDScene = preload("res://client/ui/game_hud.tscn")
const ThreatMatrixVisualizerScene = preload("res://client/ui/threat_matrix_visualizer.tscn")
const BombSafetyVisualizerScript = preload("res://client/ui/bomb_safety_visualizer.gd")

@onready var players_container = $Players
@onready var bombs_container = $Bombs
@onready var explosions_container = $Explosions
@onready var camera = $Camera2D

var player_nodes = {} # peer_id -> Node2D
var bomb_nodes = {} # bomb_id -> Node2D
var powerup_nodes = {} # powerup_id -> Node2D
var explosion_nodes = {} # explosion_id -> ExplosionRenderer
var block_nodes = {} # tile_key -> Node2D (for destructible blocks)
var wall_nodes = {} # tile_key -> Node2D (for solid walls)
var debug_tiles = {} # tile_key -> ColorRect for debugging
var my_player_id = ""
var map_rendered = false
var map_scene_instance = null # Hold reference to loaded PCK map scene
var removed_dead_players = {} # peer_id -> bool when death animation has finished and node was removed
var hud: CanvasLayer # Reference to HUD
var ai_debug_targets := {} # peer_id -> {"tile": Vector2i, "player_name": String}

# Lag mitigation systems
var local_player_controller: ClientPlayerController # Prediction for local player
var remote_player_interpolators = {} # peer_id -> EntityInterpolator for remote players
var bomb_throw_predictor: BombThrowPredictor # Power Glove throw prediction

# AI threat matrix visualization (debug)
var threat_visualizer: Node2D = null
var bomb_safety_visualizer: Node2D = null

# Input buffering: track order of pressed keys
var input_buffer = [] # Array of currently pressed direction keys in order (most recent last)
var debug_label: Label = null

func _ready():
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
	threat_visualizer.position = Vector2.ZERO  # Explicitly set to (0, 0)
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

	# Start in slow motion for debugging and inform server
	Engine.time_scale = 0.25
	if multiplayer.has_multiplayer_peer():
		multiplayer.rpc_id(1, "set_debug_timescale", 0.25)
	
	# Initialize HUD
	hud = GameHUDScene.instantiate()
	add_child(hud)
	
	# Set player name in HUD once we know it
	if ClientMain.username:
		hud.set_player_name(ClientMain.username)

	# Add minimal debug banner label to HUD
	debug_label = Label.new()
	debug_label.name = "DebugBanner"
	debug_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	debug_label.set_anchors_preset(Control.PRESET_TOP_LEFT)
	debug_label.offset_left = 8
	debug_label.offset_top = 8
	debug_label.add_theme_color_override("font_color", Color(1, 1, 1, 0.95))
	debug_label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	debug_label.add_theme_constant_override("outline_size", 2)
	hud.add_child(debug_label)
	update_debug_banner()

func update_game_state(state: Dictionary):
	# Load map configuration if present (first time only)
	if state.has("map_config") and not map_rendered:
		GameConfig.load_map_config(state.map_config)
	
	# Render map once (walls only)
	if not map_rendered and state.has("map"):
		render_map(state.map)
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
	
	# Update destructible blocks based on current map state
	if state.has("map"):
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
	
	# Update HUD timer
	if state.has("match_timer") and hud:
		hud.update_timer(state.match_timer)

	# Count alive players and update HUD
	if state.has("players") and hud:
		var alive_count = 0
		for peer_id in state.players:
			if not state.players[peer_id].get("is_dead", false):
				alive_count += 1
		hud.update_players_alive(alive_count, state.players.size())

	# Update players
	for peer_id_str in state.players:
		var player_data = state.players[peer_id_str]
		update_player(peer_id_str, player_data)

	# Update local player stats in HUD
	if state.players.has(str(multiplayer.get_unique_id())) and hud:
		var my_data = state.players[str(multiplayer.get_unique_id())]
		hud.update_player_stats(
			my_data.get("bombs_placed", 0),
			my_data.get("max_bombs", 1),
			my_data.get("bomb_range", 2),
			my_data.get("speed_multiplier", 1.0)
		)

	# Check for game over
	if state.has("match_active") and not state.match_active and hud:
		var winner_name = ""
		if state.has("winner_id") and state.winner_id:
			if state.players.has(state.winner_id):
				winner_name = state.players[state.winner_id].get("username", "Unknown")
		hud.show_game_over(winner_name)

	# Remove players no longer in state
	for peer_id in player_nodes.keys():
		if not state.players.has(peer_id):
			player_nodes[peer_id].queue_free()
			player_nodes.erase(peer_id)

	# Update bombs
	for bomb_id in state.bombs:
		var bomb_data = state.bombs[bomb_id]
		update_bomb(bomb_id, bomb_data)

	# Remove bombs no longer in state
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


	# Update explosions
	if state.has("explosions"):
		update_explosions(state.explosions)

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
					
					# Add hitbox visualization
					var hitbox = Line2D.new()
					hitbox.width = 2.0
					hitbox.default_color = Color(0, 1, 0, 0.6)
					hitbox.z_index = 101
					var radius = GameConfig.TILE_SIZE / 2.0
					var num_points = 32
					for i in range(num_points + 1):
						var angle = (i / float(num_points)) * TAU
						var point = Vector2(cos(angle), sin(angle)) * radius
						hitbox.add_point(point)
					hitbox.position = Vector2(
						col * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
						row * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
					)
					add_child(hitbox)
					
					block_nodes[tile_key] = {"block": block, "hitbox": hitbox}
	
	# Remove blocks that no longer exist (destroyed)
	for tile_key in block_nodes.keys():
		if not current_blocks.has(tile_key):
			print("[Client] Removing destroyed block: ", tile_key)
			var nodes = block_nodes[tile_key]
			nodes.block.queue_free()
			nodes.hitbox.queue_free()
			block_nodes.erase(tile_key)

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
		
		# Load Robin Hood sprite from PCK
		var player_pck_scene = load("res://player.tscn")
		if player_pck_scene:
			var sprite_root = player_pck_scene.instantiate()
			sprite_root.position = Vector2.ZERO
			player_node.add_child(sprite_root)
			# Store reference to AnimatedSprite2D for animation control
			var anim_sprite = sprite_root.get_node_or_null("AnimatedSprite2D")
			if anim_sprite:
				anim_sprite.play("state_idle")
				player_node.set_meta("animated_sprite", anim_sprite)
		else:
			# Fallback to colored rectangle if PCK not loaded
			var sprite = ColorRect.new()
			var sprite_size = GameConfig.TILE_SIZE / 2.0  # Half tile size
			sprite.size = Vector2(sprite_size, sprite_size)
			sprite.position = Vector2(-sprite_size / 2, -sprite_size / 2)
			var is_local = str(peer_id) == str(multiplayer.get_unique_id())
			sprite.color = Color(0.2, 0.6, 1.0) if is_local else Color(1.0, 0.3, 0.3)
			player_node.add_child(sprite)
		
		# Add debug arrow to show facing direction
		var arrow = Polygon2D.new()
		var arrow_scale = GameConfig.TILE_SIZE / 32.0  # Scale based on tile size
		var arrow_points = PackedVector2Array([
			Vector2(0, -15 * arrow_scale), # Top left
			Vector2(40 * arrow_scale, 0), # Tip (pointing right)
			Vector2(0, 15 * arrow_scale), # Bottom left
			Vector2(10 * arrow_scale, 0) # Inner notch
		])
		arrow.polygon = arrow_points
		arrow.color = Color(1, 0, 0, 1.0) # Bright RED
		arrow.z_index = 100
		arrow.position = Vector2(0, -50 * arrow_scale) # Above the sprite
		arrow.name = "DebugArrow"
		player_node.add_child(arrow)
		
		var label = Label.new()
		label.text = data.username
		var label_offset = GameConfig.TILE_SIZE * 0.625  # Proportional offset (40px at 64px tiles)
		label.position = Vector2(-label_offset / 2, -label_offset)
		player_node.add_child(label)
		
		# Add hitbox visualization (green square/rectangle)
		var hitbox_visual = Line2D.new()
		hitbox_visual.width = 2.0
		hitbox_visual.default_color = Color(0, 1, 0, 0.8) # Bright green
		hitbox_visual.z_index = 101
		hitbox_visual.name = "HitboxVisual"
		
		# Create square points (rectangle)
		var half_size = GameConfig.PLAYER_HALF_WIDTH
		hitbox_visual.add_point(Vector2(-half_size, -half_size)) # Top-left
		hitbox_visual.add_point(Vector2(half_size, -half_size)) # Top-right
		hitbox_visual.add_point(Vector2(half_size, half_size)) # Bottom-right
		hitbox_visual.add_point(Vector2(-half_size, half_size)) # Bottom-left
		hitbox_visual.add_point(Vector2(-half_size, -half_size)) # Close the square
		
		player_node.add_child(hitbox_visual)
		
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
	
	# Update debug arrow rotation based on facing direction
	var debug_arrow = player_node.get_node_or_null("DebugArrow")
	if debug_arrow and data.has("facing"):
		var rotation_map = {
			"RIGHT": 0.0,
			"DOWN": PI / 2.0,
			"LEFT": PI,
			"UP": - PI / 2.0
		}
		if data.facing in rotation_map:
			debug_arrow.rotation = rotation_map[data.facing]
	
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
		var direction_prefix = "south" # Default
		if data.has("facing"):
			match data.facing:
				"RIGHT":
					direction_prefix = "east"
				"DOWN":
					direction_prefix = "south"
				"LEFT":
					direction_prefix = "west"
				"UP":
					direction_prefix = "north"
		
		# Store last direction for when player stops
		player_node.set_meta("last_direction", direction_prefix)
		
		# Determine animation based on state priority
		var anim_name = ""
		var velocity = Vector2(data.velocity.x, data.velocity.y)
		var is_moving = velocity.length() >= 10.0
		
		# Priority 1: Stunned state
		if data.has("is_stunned") and data.is_stunned:
			anim_name = "state_stunned"
		# Priority 2: Panic state (near explosion)
		elif data.has("is_panicking") and data.is_panicking:
			anim_name = "state_panic"
		# Priority 3: Picking up bomb (animation)
		elif data.has("is_picking_up_bomb") and data.is_picking_up_bomb:
			# Get pickup animation direction
			var pickup_dir = "south"  # Default
			if data.has("pickup_animation_direction"):
				var pickup_vec = Vector2(data.pickup_animation_direction.x, data.pickup_animation_direction.y)
				if abs(pickup_vec.y) > abs(pickup_vec.x):
					pickup_dir = "north" if pickup_vec.y < 0 else "south"
				else:
					pickup_dir = "west" if pickup_vec.x < 0 else "east"
			anim_name = pickup_dir + "_pglove_pickup"
		# Priority 4: Carrying bomb
		elif data.has("is_carrying_bomb") and data.is_carrying_bomb:
			if is_moving:
				anim_name = direction_prefix + "_carry"
			else:
				anim_name = direction_prefix + "_hold"
		# Priority 5: Walking
		elif is_moving:
			anim_name = direction_prefix + "_walk"
		# Priority 6: Stopped (directional idle)
		else:
			anim_name = direction_prefix + "_stopped"
		
		# Play animation if it changed (with safety check)
		if animated_sprite.animation != anim_name:
			if animated_sprite.sprite_frames.has_animation(anim_name):
				animated_sprite.play(anim_name)
			else:
				# Fallback to state_idle if animation doesn't exist
				print("[GameView] Animation not found: ", anim_name, " - using state_idle")
				if animated_sprite.sprite_frames.has_animation("state_idle"):
					animated_sprite.play("state_idle")
	
	# Debug visualization removed - only direction arrow remains
	# (debug_blocking_tile, debug_check_tile, raycast lines removed for clean gameplay)
	
# DEBUG_DISABLED: 	# Update raycast line based on last_move_direction
# DEBUG_DISABLED: 	var raycast_line = player_node.get_node_or_null("RaycastLine")
# DEBUG_DISABLED: 	if raycast_line and data.has("last_move_direction"):
# DEBUG_DISABLED: 		var last_move = Vector2(data.last_move_direction.x, data.last_move_direction.y)
# DEBUG_DISABLED: 		if last_move.length() > 0.1:
# DEBUG_DISABLED: 			var motion = last_move.normalized() * 32.0  # Make it longer so it's visible
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

func update_bomb(bomb_id: String, data: Dictionary):
	var bomb_node
	
	if not bomb_nodes.has(bomb_id):
		# Create new bomb visual with SBomberman animations
		bomb_node = BombScene.instantiate()
		bomb_node.bomb_id = bomb_id
		bomb_node.name = "Bomb_" + bomb_id
		bomb_node.z_index = 10  # Render bombs above explosions
		
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
		bomb_node.visible = true  # Default to visible
	
	# Handle Power Glove states
	if data.has("state"):
		var bomb_state = data.state
		bomb_node.set_bomb_state(bomb_state)
		
		# Update Z-height for thrown bombs (server handles CARRIED positioning already)
		if bomb_state == BombRenderer.BombState.THROWN and data.has("z_height"):
			bomb_node.update_z_height(data.z_height)
		else:
			bomb_node.update_z_height(0.0)  # Reset Z height for other states

func update_explosions(explosions_data: Array):
	"""Update progressive explosions with SBomberman sprites"""
	# Track which explosions are still active in the server state
	var active_explosion_ids = {}
	
	for explosion_data in explosions_data:
		var explosion_id = explosion_data["bomb_id"]
		active_explosion_ids[explosion_id] = true
		
		# Create new explosion renderer if not exists
		if not explosion_nodes.has(explosion_id):
			var explosion_node = ExplosionRenderer.new()
			explosion_node.explosion_id = explosion_id
			explosion_node.name = "Explosion_" + explosion_id
			explosion_node.z_index = 5  # Render explosions below bombs (z_index 10)
			
			# Initialize with pattern from server
			explosion_node.initialize(
				explosion_data["pattern"],
				explosion_data["start_time"]
			)
			
			# Trigger the paired bomb's explode animation/audio the moment the explosion spawns
			if bomb_nodes.has(explosion_id):
				var linked_bomb = bomb_nodes[explosion_id]
				if is_instance_valid(linked_bomb) and linked_bomb.has_method("explode"):
					linked_bomb.explode()
			
			explosions_container.add_child(explosion_node)
			explosion_nodes[explosion_id] = explosion_node
			
			print("[GameView] Created explosion renderer: ", explosion_id, 
				  " with ", explosion_data["pattern"].size(), " tiles")
	
	# Remove explosions no longer in server state
	for explosion_id in explosion_nodes.keys():
		if not active_explosion_ids.has(explosion_id):
			explosion_nodes[explosion_id].queue_free()
			explosion_nodes.erase(explosion_id)

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
	
	var place_bomb = Input.is_action_just_pressed("ui_accept")
	var action_released = Input.is_action_just_released("ui_accept")
	
	# Note: For now, ui_accept serves dual purpose:
	# - Normal: place bomb
	# - With Power Glove: pickup on press, throw on release
	# The server will determine the appropriate action based on player state
	
	# SIMPLIFIED APPROACH: Just use server state with smooth interpolation
	# Prediction is too complex to match server's corner sliding + grid snapping
	var input_dir = Vector2(input_x, input_y)
	if my_player_id != "" and player_nodes.has(my_player_id):
		# Keep prediction state updated but don't use it for visuals
		var _predicted_state = local_player_controller.predict_movement(input_dir, delta, [])
		# Visual position comes from server via reconciliation in update_player
	
	# Send input to server (server remains authoritative)
	multiplayer.rpc_id(1, "send_player_input", {
		"input_x": input_x,
		"input_y": input_y,
		"place_bomb": place_bomb,
		"action_pressed": place_bomb,
		"action_released": action_released
	})

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
			update_debug_banner()
		elif event.keycode == Key.KEY_F4:
			if bomb_safety_visualizer:
				bomb_safety_visualizer.visible = not bomb_safety_visualizer.visible
				print("[GameView] Bomb safety visualizer: ", "ON" if bomb_safety_visualizer.visible else "OFF")
			update_debug_banner()
		elif event.keycode == Key.KEY_F5:
			# Toggle grid coordinates on threat visualizer
			if threat_visualizer and threat_visualizer.has_method("toggle_grid_coords"):
				threat_visualizer.show_grid_coords = not threat_visualizer.show_grid_coords
				print("[GameView] Threat grid coords: ", "ON" if threat_visualizer.show_grid_coords else "OFF")
		elif event.keycode == Key.KEY_F6:
			# Toggle slow motion for debugging
			var new_scale := 1.0 if Engine.time_scale < 0.99 else 0.25
			Engine.time_scale = new_scale
			print("[GameView] Debug time_scale set to ", Engine.time_scale)
			# Ask server to match time scale for consistent debug
			if multiplayer.has_multiplayer_peer():
				multiplayer.rpc_id(1, "set_debug_timescale", float(Engine.time_scale))
			update_debug_banner()
		elif event.keycode == Key.KEY_F7:
			# Toggle timing display on threat visualizer
			if threat_visualizer and threat_visualizer.has_method("toggle_timing"):
				threat_visualizer.show_timing = not threat_visualizer.show_timing
				print("[GameView] Threat timing: ", "ON" if threat_visualizer.show_timing else "OFF")
		elif event.keycode == Key.KEY_F8:
			# Request test farming spot search from server
			print("[GameView] Requesting test farming spot search (F8)")
			if multiplayer.has_multiplayer_peer():
				rpc_id(1, "test_farming_spot_broadcast")

func update_debug_banner() -> void:
	if not debug_label:
		return
	var safety_on = bomb_safety_visualizer and bomb_safety_visualizer.visible
	var threat_on = threat_visualizer and threat_visualizer.visible
	var ts = "%.2f" % Engine.time_scale
	debug_label.text = "Safety: %s  |  Threat: %s  |  TimeScale: %s" % [
		("ON" if safety_on else "OFF"),
		("ON" if threat_on else "OFF"),
		ts
	]

func render_map(map_data):
	# Get map dimensions
	var map_height = map_data.size()
	var map_width = map_data[0].size() if map_height > 0 else 0
	
	# Try to load the map from PCK first
	var pck_path = "res://res/maps/stage1.pck"
	var pck_loaded = false
	
	if FileAccess.file_exists(pck_path):
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
						wall_floor_map.visible = false  # Keep hidden
						# wall_floor_map.scale = Vector2(4.0, 4.0)
					
					# SpawnAndSoftBlockMap: Show ONLY soft blocks (source 0), hide spawn markers (source 1)
					if spawn_soft_map:
						spawn_soft_map.visible = true  # Make visible for soft blocks
						# spawn_soft_map.scale = Vector2(4.0, 4.0)
						
						# Remove spawn marker tiles (source 1) - keep only soft blocks (source 0)
						var cells_to_remove = []
						for cell in spawn_soft_map.get_used_cells():
							var source_id = spawn_soft_map.get_cell_source_id(cell)
							if source_id == 1:  # Spawn markers
								cells_to_remove.append(cell)
						
						# Erase spawn markers
						for cell in cells_to_remove:
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
					
					# Add hitbox visualization (green circle to match actual collision)
					var hitbox = Line2D.new()
					hitbox.width = 2.0
					hitbox.default_color = Color(0, 1, 0, 0.6) # Semi-transparent green
					hitbox.z_index = 101
					# Draw circle
					var radius = GameConfig.TILE_SIZE / 2.0
					var num_points = 32
					for i in range(num_points + 1):
						var angle = (i / float(num_points)) * TAU
						var point = Vector2(cos(angle), sin(angle)) * radius
						hitbox.add_point(point)
					hitbox.position = Vector2(
						col * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
						row * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
					)
					add_child(hitbox)
					
				elif tile_type == 2:
					# Destructible block - lighter brown/tan
					var block = ColorRect.new()
					block.color = Color(0.6, 0.5, 0.4)
					block.size = Vector2(GameConfig.TILE_SIZE, GameConfig.TILE_SIZE)
					block.position = Vector2(col * GameConfig.TILE_SIZE, row * GameConfig.TILE_SIZE)
					block.z_index = 0
					add_child(block)
					
					# Add hitbox visualization (green circle to match actual collision)
					var hitbox = Line2D.new()
					hitbox.width = 2.0
					hitbox.default_color = Color(0, 1, 0, 0.6) # Semi-transparent green
					hitbox.z_index = 101
					# Draw circle
					var radius = GameConfig.TILE_SIZE / 2.0
					var num_points = 32
					for i in range(num_points + 1):
						var angle = (i / float(num_points)) * TAU
						var point = Vector2(cos(angle), sin(angle)) * radius
						hitbox.add_point(point)
					hitbox.position = Vector2(
						col * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
						row * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
					)
					add_child(hitbox)
	
	# Position camera to show ENTIRE map (fixed, no following)
	# Center camera on the map
	var map_center_x = map_width * GameConfig.TILE_SIZE / 2.0
	var map_center_y = map_height * GameConfig.TILE_SIZE / 2.0
	camera.position = Vector2(map_center_x, map_center_y)
	
	# Calculate zoom to fit entire map in viewport
	# Assuming 1152x648 viewport (standard HD)
	var viewport_size = get_viewport().get_visible_rect().size
	var map_pixel_width = map_width * GameConfig.TILE_SIZE
	var map_pixel_height = map_height * GameConfig.TILE_SIZE
	
	# Calculate zoom to fit map with some padding
	var zoom_x = viewport_size.x / (map_pixel_width * 1.1) # 1.1 for 10% padding
	var zoom_y = viewport_size.y / (map_pixel_height * 1.1)
	var zoom_level = min(zoom_x, zoom_y) # Use smaller zoom to fit both dimensions
	
	camera.zoom = Vector2(zoom_level, zoom_level)
	
	print("[GameView] Camera positioned at ", camera.position, " with zoom ", camera.zoom)

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

# RPC: Receive bomb safety evaluation data from server
@rpc("any_peer", "call_remote", "unreliable")
func bomb_safety_update(safety_data: Dictionary) -> void:
	"""Update bomb safety visualizer with server's tile evaluations"""
	print("[GameView] RPC bomb_safety_update received with %d tiles" % safety_data.size())
	if bomb_safety_visualizer and bomb_safety_visualizer.has_method("update_safety_data"):
		bomb_safety_visualizer.update_safety_data(safety_data)
	else:
		print("[GameView] WARNING: bomb_safety_visualizer not ready or missing method")

func update_powerup(powerup_id: String, data: Dictionary):
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
