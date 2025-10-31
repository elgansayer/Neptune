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

# --- Saturn Bomberman Movement System ---
const TILE_SIZE = 64.0
const BASE_SPEED = 180.0  # Units per second (pixels/sec)
const WALK_MULTIPLIER = 0.5
const RUN_MULTIPLIER = 1.0
const WALK_RUN_THRESHOLD = 0.7
const INPUT_DEADZONE = 0.1
const PLAYER_HITBOX_RADIUS = 18.0  # Slightly smaller for better cornering (~28% of tile)

var player_pixel_position = Vector2.ZERO  # Continuous floating-point position
var player_velocity = Vector2.ZERO
var player_facing_direction = "DOWN"

# Network sync
var input_sequence = 0
var last_network_sync_time = 0.0
const NETWORK_SYNC_RATE = 0.05  # Send updates every 50ms (20 Hz)

# Debug
var debug_slide_active = false

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
	if not player_scenes.has(my_user_id):
		return
	
	# === PILLAR A: Dual-Speed Vector-Based Locomotion ===
	
	# Get raw input (for keyboard, this will be discrete; for gamepad, analog)
	var input_x = Input.get_axis("ui_left", "ui_right")
	var input_y = Input.get_axis("ui_up", "ui_down")
	var input_vector = Vector2(input_x, input_y)
	
	# Normalize diagonal movement to prevent faster diagonal speed
	if input_vector.length() > 1.0:
		input_vector = input_vector.normalized()
	
	# Determine walk vs run based on input magnitude
	var speed_multiplier = RUN_MULTIPLIER
	if input_vector.length() < WALK_RUN_THRESHOLD:
		speed_multiplier = WALK_MULTIPLIER
	
	# Calculate desired velocity
	var desired_velocity = input_vector * BASE_SPEED * speed_multiplier
	
	# Update facing direction (vertical priority)
	if input_vector.y < -INPUT_DEADZONE:
		player_facing_direction = "UP"
	elif input_vector.y > INPUT_DEADZONE:
		player_facing_direction = "DOWN"
	elif input_vector.x < -INPUT_DEADZONE:
		player_facing_direction = "LEFT"
	elif input_vector.x > INPUT_DEADZONE:
		player_facing_direction = "RIGHT"
	# If no input, retain last facing direction
	
	# === PILLAR B: Assisted Cornering (Wall Hugging) ===
	
	# Calculate target position if we apply full velocity
	var target_position = player_pixel_position + desired_velocity * delta
	var final_velocity = desired_velocity
	
	# First check: Can we move to target position without collision?
	if _is_position_walkable(target_position):
		# No collision - use full velocity
		final_velocity = desired_velocity
		if debug_slide_active:
			print("Slide ended - clear path")
			debug_slide_active = false
	else:
		# Collision detected - try advanced corner assistance first
		var corner_velocity = _try_corner_assistance(desired_velocity, delta)
		
		if corner_velocity != Vector2.ZERO:
			# Corner assistance found a better path
			final_velocity = corner_velocity
			if not debug_slide_active:
				print("CORNER ASSIST - auto-navigating around obstacle")
				debug_slide_active = true
		else:
			# Fall back to standard wall slide
			# Decompose velocity into X and Y components
			var velocity_x_only = Vector2(desired_velocity.x, 0)
			var velocity_y_only = Vector2(0, desired_velocity.y)
			
			# Calculate slide positions
			var slide_x_target = player_pixel_position + velocity_x_only * delta
			var slide_y_target = player_pixel_position + velocity_y_only * delta
			
			# Test each axis independently
			var can_slide_x = _is_position_walkable(slide_x_target)
			var can_slide_y = _is_position_walkable(slide_y_target)
			
			# Apply the slide resolution logic
			if can_slide_x and not can_slide_y:
				# Horizontal movement is clear, vertical is blocked
				# Slide horizontally (hugging a horizontal wall)
				final_velocity = velocity_x_only
				if not debug_slide_active:
					print("SLIDING HORIZONTALLY - hugging wall")
					debug_slide_active = true
			elif can_slide_y and not can_slide_x:
				# Vertical movement is clear, horizontal is blocked
				# Slide vertically (hugging a vertical wall)
				final_velocity = velocity_y_only
				if not debug_slide_active:
					print("SLIDING VERTICALLY - hugging wall")
					debug_slide_active = true
			elif can_slide_x and can_slide_y:
				# Both individual movements are valid but diagonal is not
				# This happens at convex corners - prefer the dominant axis
				if abs(desired_velocity.x) > abs(desired_velocity.y):
					final_velocity = velocity_x_only
				else:
					final_velocity = velocity_y_only
				if not debug_slide_active:
					print("CORNER SLIDE - both axes valid")
					debug_slide_active = true
			else:
				# Neither movement is valid (concave corner) - stop
				final_velocity = Vector2.ZERO
				if not debug_slide_active:
					print("STOPPED - concave corner")
					debug_slide_active = true
	
	# === PILLAR C: Instantaneous Input Response ===
	# Update position immediately (no acceleration/deceleration)
	player_velocity = final_velocity
	player_pixel_position += player_velocity * delta
	
	# Update visual position
	var my_player = player_scenes[my_user_id]
	my_player.position = player_pixel_position
	
	# Handle bomb placement
	var place_bomb = Input.is_action_just_pressed("ui_accept")
	
	# === Network Sync ===
	last_network_sync_time += delta
	if last_network_sync_time >= NETWORK_SYNC_RATE:
		last_network_sync_time = 0.0
		
		# Send current state to server
		input_sequence += 1
		var input_data = {
			"input_x": input_x,
			"input_y": input_y,
			"position_x": player_pixel_position.x,
			"position_y": player_pixel_position.y,
			"place_bomb": place_bomb,
			"seq": input_sequence
		}
		nakama_client.send_player_input(input_data)
	
	if place_bomb:
		# Send bomb placement immediately
		input_sequence += 1
		var bomb_input = {
			"input_x": 0,
			"input_y": 0,
			"position_x": player_pixel_position.x,
			"position_y": player_pixel_position.y,
			"place_bomb": true,
			"seq": input_sequence
		}
		nakama_client.send_player_input(bomb_input)

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

# Pixel-based collision detection (Saturn Bomberman style)
func _is_position_walkable(pixel_pos: Vector2) -> bool:
	if not game_state.has("grid"):
		return true  # No grid loaded yet
	
	var grid = game_state.grid
	
	# Check collision in a circular hitbox around the player
	# Sample 8 points around circle + center for better coverage
	var check_points = [
		pixel_pos,  # Center
		pixel_pos + Vector2(PLAYER_HITBOX_RADIUS, 0),  # Right
		pixel_pos + Vector2(-PLAYER_HITBOX_RADIUS, 0),  # Left
		pixel_pos + Vector2(0, PLAYER_HITBOX_RADIUS),  # Down
		pixel_pos + Vector2(0, -PLAYER_HITBOX_RADIUS),  # Up
		# Add diagonal checks for better corner detection
		pixel_pos + Vector2(PLAYER_HITBOX_RADIUS * 0.707, PLAYER_HITBOX_RADIUS * 0.707),  # Down-Right
		pixel_pos + Vector2(-PLAYER_HITBOX_RADIUS * 0.707, PLAYER_HITBOX_RADIUS * 0.707),  # Down-Left
		pixel_pos + Vector2(PLAYER_HITBOX_RADIUS * 0.707, -PLAYER_HITBOX_RADIUS * 0.707),  # Up-Right
		pixel_pos + Vector2(-PLAYER_HITBOX_RADIUS * 0.707, -PLAYER_HITBOX_RADIUS * 0.707)  # Up-Left
	]
	
	for point in check_points:
		var grid_x = int(floor(point.x / TILE_SIZE))
		var grid_y = int(floor(point.y / TILE_SIZE))
		
		# Out of bounds check
		if grid_y < 0 or grid_y >= grid.size() or grid_x < 0 or grid_x >= grid[0].size():
			return false
		
		# Wall/block check
		if grid[grid_y][grid_x] != 0:
			return false
		
		# Bomb collision check
		if game_state.has("bombs"):
			for bomb in game_state.bombs:
				var bomb_center = Vector2(
					bomb.position.x * TILE_SIZE + TILE_SIZE / 2,
					bomb.position.y * TILE_SIZE + TILE_SIZE / 2
				)
				if point.distance_to(bomb_center) < (PLAYER_HITBOX_RADIUS + 25.0):
					return false
	
	return true

# Advanced corner assistance - predicts player intent and helps navigate corners
# Example: Player at position halfway past block A, pressing RIGHT
# System detects: "Player wants to go RIGHT but is blocked, they're >50% past the obstacle"
# Action: Temporarily move UP to clear the corner, then resume RIGHT movement
func _try_corner_assistance(desired_velocity: Vector2, delta: float) -> Vector2:
	if not game_state.has("grid"):
		return Vector2.ZERO
	
	var grid = game_state.grid
	
	# Get the grid cell we're trying to move into
	var target_pos = player_pixel_position + desired_velocity * delta
	var target_grid_x = int(floor(target_pos.x / TILE_SIZE))
	var target_grid_y = int(floor(target_pos.y / TILE_SIZE))
	
	# Get current grid position
	var current_grid_x = int(floor(player_pixel_position.x / TILE_SIZE))
	var current_grid_y = int(floor(player_pixel_position.y / TILE_SIZE))
	
	# Only assist if we're trying to move into an adjacent cell
	var dx_grid = target_grid_x - current_grid_x
	var dy_grid = target_grid_y - current_grid_y
	
	# Calculate player's position within their current tile (0.0 to 1.0)
	var tile_local_x = (player_pixel_position.x - current_grid_x * TILE_SIZE) / TILE_SIZE
	var tile_local_y = (player_pixel_position.y - current_grid_y * TILE_SIZE) / TILE_SIZE
	
	# CASE 1: Trying to move RIGHT, blocked, but we're >50% up in the tile
	if dx_grid > 0 and dy_grid == 0:
		# Check if blocked to the right
		if target_grid_x < grid[0].size() and target_grid_y >= 0 and target_grid_y < grid.size():
			if grid[target_grid_y][target_grid_x] != 0:
				# Blocked! Check if we're in the top half of our current tile
				if tile_local_y < 0.5:
					# Try moving UP to clear the corner
					var up_velocity = Vector2(0, -BASE_SPEED * (1.0 if desired_velocity.length() > BASE_SPEED * 0.7 else 0.5))
					var up_target = player_pixel_position + up_velocity * delta
					if _is_position_walkable(up_target):
						return up_velocity
	
	# CASE 2: Trying to move LEFT, blocked, but we're >50% up in the tile
	if dx_grid < 0 and dy_grid == 0:
		if target_grid_x >= 0 and target_grid_y >= 0 and target_grid_y < grid.size():
			if grid[target_grid_y][target_grid_x] != 0:
				if tile_local_y < 0.5:
					var up_velocity = Vector2(0, -BASE_SPEED * (1.0 if desired_velocity.length() > BASE_SPEED * 0.7 else 0.5))
					var up_target = player_pixel_position + up_velocity * delta
					if _is_position_walkable(up_target):
						return up_velocity
	
	# CASE 3: Trying to move DOWN, blocked, but we're >50% to the right in the tile
	if dy_grid > 0 and dx_grid == 0:
		if target_grid_y < grid.size() and target_grid_x >= 0 and target_grid_x < grid[0].size():
			if grid[target_grid_y][target_grid_x] != 0:
				if tile_local_x > 0.5:
					var right_velocity = Vector2(BASE_SPEED * (1.0 if desired_velocity.length() > BASE_SPEED * 0.7 else 0.5), 0)
					var right_target = player_pixel_position + right_velocity * delta
					if _is_position_walkable(right_target):
						return right_velocity
	
	# CASE 4: Trying to move UP, blocked, but we're >50% to the right in the tile
	if dy_grid < 0 and dx_grid == 0:
		if target_grid_y >= 0 and target_grid_x >= 0 and target_grid_x < grid[0].size():
			if grid[target_grid_y][target_grid_x] != 0:
				if tile_local_x > 0.5:
					var right_velocity = Vector2(BASE_SPEED * (1.0 if desired_velocity.length() > BASE_SPEED * 0.7 else 0.5), 0)
					var right_target = player_pixel_position + right_velocity * delta
					if _is_position_walkable(right_target):
						return right_velocity
	
	# No corner assistance needed
	return Vector2.ZERO

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
	
	# Server sends pixel positions, accept them with some smoothing
	if my_server_state.has("pixel_position"):
		var server_pixel_pos = Vector2(
			my_server_state.pixel_position.x,
			my_server_state.pixel_position.y
		)
		
		# If server position differs significantly, snap to it (anti-cheat)
		var position_error = player_pixel_position.distance_to(server_pixel_pos)
		if position_error > 100.0:  # More than ~1.5 tiles off
			player_pixel_position = server_pixel_pos
			print("Position corrected by server: error was ", position_error)
	else:
		# Fallback: server sends grid position, convert to pixels
		var server_pixel_pos = Vector2(
			my_server_state.position.x * TILE_SIZE + TILE_SIZE / 2,
			my_server_state.position.y * TILE_SIZE + TILE_SIZE / 2
		)
		player_pixel_position = server_pixel_pos

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

		# Update positions
		if player_id == my_user_id:
			# Initialize our pixel position if not set
			if player_pixel_position == Vector2.ZERO:
				if player_data.has("pixel_position"):
					player_pixel_position = Vector2(
						player_data.pixel_position.x,
						player_data.pixel_position.y
					)
				else:
					player_pixel_position = Vector2(
						player_data.position.x * TILE_SIZE + TILE_SIZE / 2,
						player_data.position.y * TILE_SIZE + TILE_SIZE / 2
					)
			# Position is updated in _physics_process
		else:
			# Other players: use server position directly
			if player_data.has("pixel_position"):
				player_node.position = Vector2(
					player_data.pixel_position.x,
					player_data.pixel_position.y
				)
			else:
				player_node.position = Vector2(
					player_data.position.x * TILE_SIZE + TILE_SIZE / 2,
					player_data.position.y * TILE_SIZE + TILE_SIZE / 2
				)

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
