extends Node

@onready var nakama_client = NakamaService
var grid_rendered = false

# --- State Variables ---
var game_state = {}
var player_scenes = {}
var bomb_scenes = {}
var explosion_scenes = {}
var powerup_scenes = {}
var character_data = {}
var my_user_id = ""

# --- Prediction & Reconciliation ---
var input_sequence = 0
var pending_inputs = []
var last_input_time = 0.0
var input_cooldown = 0.1  # 100ms between inputs (10 inputs per second max)
var predicted_position = Vector2i(-1, -1)  # Grid coordinates

# --- Godot Lifecycle ---

func _ready():
	print("=== GameManager _ready() called ===")
	# Get session info if already authenticated
	if nakama_client.session:
		my_user_id = nakama_client.session.user_id
		print("GameManager: User ID is ", my_user_id)
		print("GameManager: Match ID is ", nakama_client.match_id)
	else:
		print("GameManager: No session yet, connecting signal")
		nakama_client.authenticated.connect(_on_authenticated)
	
	nakama_client.match_data_received.connect(_on_match_data_received)
	_load_character_data()
	print("GameManager ready. Waiting for server state...")
	print("GameManager: Socket exists? ", nakama_client.socket != null)
	print("GameManager: Match ID: ", nakama_client.match_id)

func _on_authenticated(session, _is_new_user):
	my_user_id = session.user_id
func _load_character_data():
	var dir = DirAccess.open("res://characters")
	if dir:
		dir.list_dir_begin()
		var file_name = dir.get_next()
		while file_name != "":
			if not dir.current_is_dir() and file_name.ends_with(".json"):
				var file = FileAccess.open("res://characters/" + file_name, FileAccess.READ)
				var content = file.get_as_text()
				file.close()
				var json = JSON.parse_string(content)
				if json:
					character_data[json.name] = json
			file_name = dir.get_next()
	else:
		print("An error occurred when trying to access the path.")


func _physics_process(delta):
	# Throttle input to prevent super fast movement
	last_input_time += delta
	if last_input_time < input_cooldown:
		return
		
	var dx = int(Input.is_action_pressed("ui_right")) - int(Input.is_action_pressed("ui_left"))
	var dy = int(Input.is_action_pressed("ui_down")) - int(Input.is_action_pressed("ui_up"))
	var place_bomb = Input.is_action_just_pressed("ui_accept")

	if dx != 0 or dy != 0 or place_bomb:
		last_input_time = 0.0  # Reset cooldown
		input_sequence += 1
		var input_data = {
			"dx": dx,
			"dy": dy,
			"place_bomb": place_bomb,
			"seq": input_sequence
		}
		nakama_client.send_player_input(input_data)
		pending_inputs.append(input_data)
		
		# Client-side prediction with collision detection
		_apply_input_prediction(input_data)

# --- Signal Handlers ---

func _on_match_data_received(data):
	if data.op_code == 2: # State Sync
		game_state = data.data
		print("State update - Players: ", game_state.get("players", {}).size(), 
			  " Bombs: ", game_state.get("bombs", []).size(),
			  " Grid rows: ", game_state.get("grid", []).size())
		_reconcile_local_player(game_state.get("players", {}))
		_update_players(game_state.get("players", {}))
		_update_bombs(game_state.get("bombs", []))
		_update_explosions(game_state.get("explosions", []))
		_update_grid(game_state.get("grid", []))
		_update_powerups(game_state.get("powerUps", []))

# --- Private Update Functions ---

func _update_powerups(server_powerups):
	var current_client_powerups = powerup_scenes.keys()

	for i in range(server_powerups.size()):
		var powerup_data = server_powerups[i]
		var powerup_id = "%s_%s" % [powerup_data.position.x, powerup_data.position.y]
		var powerup_node

		if not powerup_scenes.has(powerup_id):
			print("Spawning powerup: ", powerup_id)
			powerup_node = Area2D.new()
			powerup_node.name = powerup_id
			
			var sprite = Sprite2D.new()
			sprite.texture = load("res://icon.svg") # Placeholder texture
			powerup_node.add_child(sprite)
			
			# Add a CollisionShape2D for the Area2D
			var collision_shape = CollisionShape2D.new()
			var circle_shape = CircleShape2D.new()
			circle_shape.radius = 32.0 # Adjust as needed
			collision_shape.shape = circle_shape
			powerup_node.add_child(collision_shape)
			
			# TODO: Change texture based on power-up type
			add_child(powerup_node)
			powerup_scenes[powerup_id] = powerup_node
		else:
			powerup_node = powerup_scenes[powerup_id]
			current_client_powerups.erase(powerup_id)

		powerup_node.position = Vector2(powerup_data.position.x * 64, powerup_data.position.y * 64)

	for powerup_id in current_client_powerups:
		print("Removing powerup: ", powerup_id)
		powerup_scenes[powerup_id].queue_free()
		powerup_scenes.erase(powerup_id)

func _update_bombs(server_bombs):
	var current_client_bombs = bomb_scenes.keys()
	
	for bomb_data in server_bombs:
		var bomb_id = str(bomb_data.id)
		var bomb_node
		
		if not bomb_scenes.has(bomb_id):
			print("Spawning bomb: ", bomb_id)
			bomb_node = Node2D.new()
			bomb_node.name = "Bomb_" + bomb_id
			
			# Create bomb sprite
			var sprite = Sprite2D.new()
			sprite.texture = load("res://icon.svg")  # Placeholder
			sprite.modulate = Color.BLACK
			sprite.scale = Vector2(0.5, 0.5)
			bomb_node.add_child(sprite)
			
			# Add timer label
			var new_label = Label.new()
			new_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			new_label.position = Vector2(-20, -40)
			bomb_node.add_child(new_label)
			
			add_child(bomb_node)
			bomb_scenes[bomb_id] = bomb_node
		else:
			bomb_node = bomb_scenes[bomb_id]
			current_client_bombs.erase(bomb_id)
		
		bomb_node.position = Vector2(bomb_data.position.x * 64 + 32, bomb_data.position.y * 64 + 32)
		
		# Update timer display
		var existing_label = bomb_node.get_child(1) as Label
		var seconds_left = ceil(bomb_data.timer / 20.0)
		existing_label.text = str(seconds_left)
	
	# Remove bombs that no longer exist
	for bomb_id in current_client_bombs:
		print("Removing bomb: ", bomb_id)
		bomb_scenes[bomb_id].queue_free()
		bomb_scenes.erase(bomb_id)

# Client-side collision detection helper
func _is_walkable(x: int, y: int) -> bool:
	if not game_state.has("grid"):
		return true  # No grid loaded yet, allow movement
	
	var grid = game_state.grid
	if y < 0 or y >= grid.size() or x < 0 or x >= grid[0].size():
		return false  # Out of bounds
	
	if grid[y][x] != 0:
		return false  # Wall or block
	
	# Check for bombs at position
	if game_state.has("bombs"):
		for bomb in game_state.bombs:
			if bomb.position.x == x and bomb.position.y == y:
				return false
	
	return true

# Apply client-side prediction for an input
func _apply_input_prediction(input: Dictionary):
	if not player_scenes.has(my_user_id):
		return
	
	if predicted_position.x < 0:  # Not initialized yet
		return
	
	if input.dx != 0 or input.dy != 0:
		var new_x = predicted_position.x + input.dx
		var new_y = predicted_position.y + input.dy
		if _is_walkable(new_x, new_y):
			predicted_position = Vector2i(new_x, new_y)
			var my_player = player_scenes[my_user_id]
			my_player.position = Vector2(predicted_position.x * 64 + 32, predicted_position.y * 64 + 32)

func _update_explosions(server_explosions):
	# Clear old explosions
	for explosion_id in explosion_scenes.keys():
		explosion_scenes[explosion_id].queue_free()
	explosion_scenes.clear()
	
	# Create new explosions
	for i in range(server_explosions.size()):
		var explosion_data = server_explosions[i]
		var explosion_id = "explosion_" + str(i)
		
		var explosion_container = Node2D.new()
		explosion_container.name = explosion_id
		
		for tile in explosion_data.tiles:
			var sprite = Sprite2D.new()
			sprite.texture = load("res://icon.svg")  # Placeholder
			sprite.modulate = Color(1.0, 0.5, 0.0, 0.7)  # Orange with transparency
			sprite.position = Vector2(tile.x * 64 + 32, tile.y * 64 + 32)
			sprite.scale = Vector2(0.8, 0.8)
			explosion_container.add_child(sprite)
		
		add_child(explosion_container)
		explosion_scenes[explosion_id] = explosion_container

func _reconcile_local_player(server_players):
	if not server_players.has(my_user_id):
		return

	var my_server_state = server_players[my_user_id]
	var my_client_player = player_scenes.get(my_user_id)

	if my_client_player:
		# Remove inputs that the server has already processed
		var last_processed_seq = my_server_state.get("lastProcessedSequence", 0)
		pending_inputs = pending_inputs.filter(func(input): return input.seq > last_processed_seq)

		# Start with authoritative server position (grid coordinates)
		var server_grid_pos = Vector2i(my_server_state.position.x, my_server_state.position.y)
		predicted_position = server_grid_pos
		
		# Re-apply pending inputs with client-side collision detection
		for input in pending_inputs:
			if input.dx != 0 or input.dy != 0:
				var new_x = predicted_position.x + input.dx
				var new_y = predicted_position.y + input.dy
				if _is_walkable(new_x, new_y):
					predicted_position = Vector2i(new_x, new_y)
		
		# Update visual position to predicted position
		my_client_player.position = Vector2(predicted_position.x * 64 + 32, predicted_position.y * 64 + 32)

func _update_players(server_players):
	var current_client_players = player_scenes.keys()

	for player_id in server_players:
		var player_data = server_players[player_id]
		var player_node

		if not player_scenes.has(player_id):
			print("Creating player node for: ", player_id)
			player_node = Node2D.new()
			player_node.name = player_id
			
			# Create a simple sprite for the player
			var sprite = Sprite2D.new()
			sprite.texture = load("res://icon.svg")
			sprite.scale = Vector2(0.4, 0.4)
			
			# Color players differently - you vs others
			if player_id == my_user_id:
				sprite.modulate = Color.GREEN
			else:
				sprite.modulate = Color.RED
			
			player_node.add_child(sprite)
			
			# Add username label
			var label = Label.new()
			label.text = player_data.username
			label.position = Vector2(-30, -50)
			label.add_theme_color_override("font_color", Color.WHITE)
			player_node.add_child(label)
			
			add_child(player_node)
			player_scenes[player_id] = player_node
		else:
			player_node = player_scenes[player_id]
			current_client_players.erase(player_id)

		player_node.visible = player_data.isAlive

		# For other players (not us), directly set their position from server
		# For local player, position is set in _reconcile_local_player
		if player_id != my_user_id:
			player_node.position = Vector2(player_data.position.x * 64 + 32, player_data.position.y * 64 + 32)

	for player_id in current_client_players:
		print("Removing player: ", player_id)
		player_scenes[player_id].queue_free()
		player_scenes.erase(player_id)

func _update_grid(grid_data):
	if grid_rendered:
		return
	
	grid_rendered = true
	print("Drawing initial grid with ", grid_data.size(), " rows")
	
	for y in range(grid_data.size()):
		for x in range(grid_data[y].size()):
			var tile_type = grid_data[y][x]
			if tile_type > 0:
				var tile_sprite = Sprite2D.new()
				tile_sprite.texture = load("res://icon.svg")
				tile_sprite.position = Vector2(x * 64 + 32, y * 64 + 32)
				tile_sprite.scale = Vector2(0.5, 0.5)
				
				# Color based on tile type
				if tile_type == 1:  # Soft block
					tile_sprite.modulate = Color(0.6, 0.4, 0.2)  # Brown
				elif tile_type == 2:  # Hard block
					tile_sprite.modulate = Color(0.3, 0.3, 0.3)  # Dark gray
				
				add_child(tile_sprite)
