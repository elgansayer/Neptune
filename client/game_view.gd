extends Node2D

# Client-side game display
# Receives state from server and renders it

const Constants = preload("res://shared/constants.gd")

@onready var players_container = $Players
@onready var bombs_container = $Bombs
@onready var explosions_container = $Explosions
@onready var camera = $Camera2D

var player_nodes = {}  # peer_id -> Node2D
var bomb_nodes = {}  # bomb_id -> Node2D
var explosion_nodes = {}  # cell_key -> Node2D
var debug_tiles = {}  # tile_key -> ColorRect for debugging
var my_player_id = ""
var map_rendered = false

# Input buffering: track order of pressed keys
var input_buffer = []  # Array of currently pressed direction keys in order (most recent last)

func _ready():
	# Set up camera
	camera.enabled = true

func update_game_state(state: Dictionary):
	# Render map once
	if not map_rendered and state.has("map"):
		render_map(state.map)
		map_rendered = true
	
	# Update players
	for peer_id_str in state.players:
		var player_data = state.players[peer_id_str]
		update_player(peer_id_str, player_data)
	
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
	
	# Update explosions
	if state.has("explosions"):
		update_explosions(state.explosions)

func update_player(peer_id: String, data: Dictionary):
	var player_node
	
	if not player_nodes.has(peer_id):
		# Create new player visual
		player_node = Node2D.new()
		player_node.name = "Player_" + peer_id
		
		var sprite = Sprite2D.new()
		sprite.texture = load("res://icon.svg")
		sprite.scale = Vector2(0.4, 0.4)
		player_node.add_child(sprite)
		
		# Add debug arrow to show facing direction
		var arrow = Polygon2D.new()
		var arrow_points = PackedVector2Array([
			Vector2(0, -15),      # Top left
			Vector2(40, 0),       # Tip (pointing right)
			Vector2(0, 15),       # Bottom left
			Vector2(10, 0)        # Inner notch
		])
		arrow.polygon = arrow_points
		arrow.color = Color(1, 0, 0, 1.0)  # Bright RED
		arrow.z_index = 100
		arrow.position = Vector2(0, -50)  # Above the sprite
		arrow.name = "DebugArrow"
		player_node.add_child(arrow)
		
		var label = Label.new()
		label.text = data.username
		label.position = Vector2(-30, -40)
		player_node.add_child(label)
		
		# Add hitbox visualization (green circle)
		var hitbox_visual = Line2D.new()
		hitbox_visual.width = 2.0
		hitbox_visual.default_color = Color(0, 1, 0, 0.8)  # Bright green
		hitbox_visual.z_index = 101
		hitbox_visual.name = "HitboxVisual"
		
		# Create circle points
		var radius = Constants.PLAYER_HALF_WIDTH
		var num_points = 32
		for i in range(num_points + 1):
			var angle = (i / float(num_points)) * TAU
			var point = Vector2(cos(angle), sin(angle)) * radius
			hitbox_visual.add_point(point)
		
		player_node.add_child(hitbox_visual)
		
		# Add raycast visualization line
		var raycast_debug_line = Line2D.new()
		# Width = collision shape diameter to show actual raycast width
		raycast_debug_line.width = Constants.PLAYER_HALF_WIDTH * 2.0  # 56px diameter
		raycast_debug_line.default_color = Color(0, 1, 1, 1.0)  # Cyan
		raycast_debug_line.z_index = 100  # Fixed: within valid range
		raycast_debug_line.antialiased = true
		raycast_debug_line.name = "RaycastLine"
		player_node.add_child(raycast_debug_line)
		
		# Add ShapeCast2D visualization (showing the collision check shape)
		var shapecast_visual = Line2D.new()
		shapecast_visual.width = Constants.PLAYER_HALF_WIDTH * 2.0  # Same size as player
		shapecast_visual.default_color = Color(1, 0, 0, 0.6)  # Red by default
		shapecast_visual.z_index = 101
		shapecast_visual.antialiased = true
		shapecast_visual.name = "ShapeCastVisual"
		player_node.add_child(shapecast_visual)
		
		players_container.add_child(player_node)
		player_nodes[peer_id] = player_node
		
		# If this is our player, follow with camera
		if peer_id == str(multiplayer.get_unique_id()):
			my_player_id = peer_id
	else:
		player_node = player_nodes[peer_id]
	
	# Update position (smooth interpolation could be added here)
	var target_pos = Vector2(data.position.x, data.position.y)
	player_node.position = target_pos
	
	# Update debug arrow rotation based on facing direction
	var debug_arrow = player_node.get_node_or_null("DebugArrow")
	if debug_arrow and data.has("facing"):
		var rotation_map = {
			"RIGHT": 0.0,
			"DOWN": PI / 2.0,
			"LEFT": PI,
			"UP": -PI / 2.0
		}
		if data.facing in rotation_map:
			debug_arrow.rotation = rotation_map[data.facing]
	
	# Show debug tiles if present in state
	if data.has("debug_blocking_tile"):
		var blocking_data = data.debug_blocking_tile
		show_debug_tile(Vector2i(blocking_data.x, blocking_data.y), Color(1, 0, 0, 0.7))  # RED for blocking tile
	
	if data.has("debug_check_tile"):
		var desired_data = data.debug_check_tile
		show_debug_tile(Vector2i(desired_data.x, desired_data.y), Color(1, 1, 0, 0.7))  # YELLOW for desired tile
	
	# Update raycast line based on last_move_direction
	var raycast_line = player_node.get_node_or_null("RaycastLine")
	if raycast_line and data.has("last_move_direction"):
		var last_move = Vector2(data.last_move_direction.x, data.last_move_direction.y)
		if last_move.length() > 0.1:
			var motion = last_move.normalized() * 32.0  # Make it longer so it's visible
			raycast_line.clear_points()
			raycast_line.add_point(Vector2.ZERO)
			raycast_line.add_point(motion)
		else:
			raycast_line.clear_points()
	
	# Update ShapeCast2D visual if we have shape_cast data
	var shapecast_visual = player_node.get_node_or_null("ShapeCastVisual")
	if shapecast_visual and data.has("shape_cast_target"):
		var target = Vector2(data.shape_cast_target.x, data.shape_cast_target.y)
		var is_colliding = data.get("shape_cast_colliding", false)
		
		# Update color based on collision state
		shapecast_visual.default_color = Color(1, 0, 0, 0.6) if is_colliding else Color(0, 1, 0, 0.4)
		
		# Draw the shape cast line
		if target.length() > 0.1:
			shapecast_visual.clear_points()
			shapecast_visual.add_point(Vector2.ZERO)
			shapecast_visual.add_point(target)
		else:
			shapecast_visual.clear_points()
	
	# Update camera to follow our player
	if peer_id == my_player_id:
		camera.position = target_pos

func update_bomb(bomb_id: String, data: Dictionary):
	var bomb_node
	
	if not bomb_nodes.has(bomb_id):
		# Create new bomb visual
		bomb_node = Node2D.new()
		bomb_node.name = "Bomb_" + bomb_id
		
		var sprite = Sprite2D.new()
		sprite.texture = load("res://icon.svg")
		sprite.scale = Vector2(0.35, 0.35)
		sprite.modulate = Color(0.1, 0.1, 0.1)  # Dark/black for bomb
		bomb_node.add_child(sprite)
		
		# Add bomb hitbox visualization (green circle)
		var hitbox_visual = Line2D.new()
		hitbox_visual.width = 2.0
		hitbox_visual.default_color = Color(0, 1, 0, 0.8)  # Bright green
		hitbox_visual.z_index = 101
		
		# Create circle points
		var radius = Constants.PLAYER_HALF_WIDTH  # Bombs use same size as player
		var num_points = 32
		for i in range(num_points + 1):
			var angle = (i / float(num_points)) * TAU
			var point = Vector2(cos(angle), sin(angle)) * radius
			hitbox_visual.add_point(point)
		
		bomb_node.add_child(hitbox_visual)
		
		var label = Label.new()
		label.position = Vector2(-15, -35)
		label.add_theme_font_size_override("font_size", 20)
		bomb_node.add_child(label)
		
		bombs_container.add_child(bomb_node)
		bomb_nodes[bomb_id] = bomb_node
	else:
		bomb_node = bomb_nodes[bomb_id]
	
	# Update position and timer
	bomb_node.position = Vector2(data.position.x, data.position.y)
	var timer_label = bomb_node.get_child(1) as Label
	if timer_label:
		timer_label.text = "%.1f" % data.timer

func update_explosions(explosions_data: Array):
	# Clear all current explosion nodes
	for cell_key in explosion_nodes.keys():
		explosion_nodes[cell_key].queue_free()
	explosion_nodes.clear()
	
	# Create new explosion sprites for each cell
	for explosion_cell in explosions_data:
		var cell_key = "%d,%d" % [explosion_cell.x, explosion_cell.y]
		
		var explosion_node = Node2D.new()
		
		# Create explosion visual (bright orange/red circle)
		var sprite = Sprite2D.new()
		sprite.texture = preload("res://icon.svg")
		sprite.modulate = Color(1.0, 0.4, 0.0, 0.8)  # Orange with transparency
		sprite.scale = Vector2(0.5, 0.5)
		explosion_node.add_child(sprite)
		
		explosion_node.position = Vector2(
			explosion_cell.x * Constants.TILE_SIZE + Constants.TILE_SIZE / 2.0,
			explosion_cell.y * Constants.TILE_SIZE + Constants.TILE_SIZE / 2.0
		)
		
		explosions_container.add_child(explosion_node)
		explosion_nodes[cell_key] = explosion_node

func _physics_process(_delta):
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
		var current_dir = input_buffer[input_buffer.size() - 1]  # Last element = most recent
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
	
	# Always send input state to server (including zero input when keys released)
	get_node("/root/ServerMain").rpc_id(1, "send_player_input", {
		"input_x": input_x,
		"input_y": input_y,
		"place_bomb": place_bomb
	})

func render_map(map_data):
	# Draw background for the play area
	var bg = ColorRect.new()
	bg.color = Color(0.15, 0.25, 0.15)  # Dark green background
	bg.size = Vector2(Constants.TILE_SIZE * 13, Constants.TILE_SIZE * 11)
	bg.position = Vector2.ZERO
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
				wall.size = Vector2(Constants.TILE_SIZE, Constants.TILE_SIZE)
				wall.position = Vector2(col * Constants.TILE_SIZE, row * Constants.TILE_SIZE)
				wall.z_index = 0
				add_child(wall)
				
				# Add hitbox visualization (green circle to match actual collision)
				var hitbox = Line2D.new()
				hitbox.width = 2.0
				hitbox.default_color = Color(0, 1, 0, 0.6)  # Semi-transparent green
				hitbox.z_index = 101
				# Draw circle
				var radius = Constants.TILE_SIZE / 2.0
				var num_points = 32
				for i in range(num_points + 1):
					var angle = (i / float(num_points)) * TAU
					var point = Vector2(cos(angle), sin(angle)) * radius
					hitbox.add_point(point)
				hitbox.position = Vector2(
					col * Constants.TILE_SIZE + Constants.TILE_SIZE / 2.0,
					row * Constants.TILE_SIZE + Constants.TILE_SIZE / 2.0
				)
				add_child(hitbox)
				
			elif tile_type == 2:
				# Destructible block - lighter brown/tan
				var block = ColorRect.new()
				block.color = Color(0.6, 0.5, 0.4)
				block.size = Vector2(Constants.TILE_SIZE, Constants.TILE_SIZE)
				block.position = Vector2(col * Constants.TILE_SIZE, row * Constants.TILE_SIZE)
				block.z_index = 0
				add_child(block)
				
				# Add hitbox visualization (green circle to match actual collision)
				var hitbox = Line2D.new()
				hitbox.width = 2.0
				hitbox.default_color = Color(0, 1, 0, 0.6)  # Semi-transparent green
				hitbox.z_index = 101
				# Draw circle
				var radius = Constants.TILE_SIZE / 2.0
				var num_points = 32
				for i in range(num_points + 1):
					var angle = (i / float(num_points)) * TAU
					var point = Vector2(cos(angle), sin(angle)) * radius
					hitbox.add_point(point)
				hitbox.position = Vector2(
					col * Constants.TILE_SIZE + Constants.TILE_SIZE / 2.0,
					row * Constants.TILE_SIZE + Constants.TILE_SIZE / 2.0
				)
				add_child(hitbox)

func show_debug_tile(tile_pos: Vector2i, color: Color):
	"""Show a colored overlay on a tile for debugging"""
	var tile_key = "%d,%d" % [tile_pos.x, tile_pos.y]
	
	# Remove old debug tile if exists
	if debug_tiles.has(tile_key):
		debug_tiles[tile_key].queue_free()
		debug_tiles.erase(tile_key)
	
	# Create new debug overlay
	var debug_rect = ColorRect.new()
	debug_rect.size = Vector2(Constants.TILE_SIZE, Constants.TILE_SIZE)
	debug_rect.color = color
	debug_rect.position = Vector2(
		tile_pos.x * Constants.TILE_SIZE,
		tile_pos.y * Constants.TILE_SIZE
	)
	debug_rect.z_index = 100  # On top of everything
	
	# Add to scene
	add_child(debug_rect)
	debug_tiles[tile_key] = debug_rect
	
	# Auto-remove after a short time
	await get_tree().create_timer(0.15).timeout
	if is_instance_valid(debug_rect):
		debug_rect.queue_free()
	if debug_tiles.has(tile_key):
		debug_tiles.erase(tile_key)

