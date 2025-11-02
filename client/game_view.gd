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
var my_player_id = ""
var map_rendered = false

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
		
		var label = Label.new()
		label.text = data.username
		label.position = Vector2(-30, -40)
		player_node.add_child(label)
		
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
	# Continuously send input state to server
	var input_x = 0.0
	var input_y = 0.0
	var place_bomb = false
	
	if Input.is_action_pressed("ui_right"):
		input_x = 1.0
	elif Input.is_action_pressed("ui_left"):
		input_x = -1.0
	
	if Input.is_action_pressed("ui_down"):
		input_y = 1.0
	elif Input.is_action_pressed("ui_up"):
		input_y = -1.0
	
	if Input.is_action_just_pressed("ui_accept"):
		place_bomb = true
	
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
			elif tile_type == 2:
				# Destructible block - brown/tan
				var block = ColorRect.new()
				block.color = Color(0.6, 0.4, 0.2)
				block.size = Vector2(Constants.TILE_SIZE - 4, Constants.TILE_SIZE - 4)
				block.position = Vector2(col * Constants.TILE_SIZE + 2, row * Constants.TILE_SIZE + 2)
				block.z_index = 0
				add_child(block)
