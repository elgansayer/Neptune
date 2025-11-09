extends Node
class_name PlayerLogManager

## Player Data Logging System for AI Training
## Records human player actions, positions, context, and outcomes
## Exports data to JSON/CSV for imitation learning and reinforcement learning training

const Constants = preload("res://shared/constants.gd")

# Logging settings
var enabled: bool = false
var log_frequency: float = 0.1  # Log every 100ms
var last_log_time: float = 0.0
var session_id: String = ""
var log_data: Array = []

# File paths
var logs_directory: String = "user://player_logs/"
var current_log_file: String = ""

# References
var game_instance: Node2D
var tracked_players: Dictionary = {}  # player_id -> player_data
var danger_mapper  # Optional: for context enrichment

# Action types
enum ActionType {
	MOVE_UP,
	MOVE_DOWN,
	MOVE_LEFT,
	MOVE_RIGHT,
	PLACE_BOMB,
	PICKUP_POWERUP,
	IDLE,
	DIED,
	KILLED_ENEMY
}

func _init(game_ref: Node2D = null):
	game_instance = game_ref
	_ensure_logs_directory()

func _ensure_logs_directory():
	var dir = DirAccess.open("user://")
	if not dir.dir_exists("player_logs"):
		dir.make_dir("player_logs")

## Start logging session
func start_session(session_name: String = ""):
	if session_name == "":
		session_id = _generate_session_id()
	else:
		session_id = session_name
	
	current_log_file = logs_directory + session_id + ".json"
	log_data.clear()
	enabled = true
	last_log_time = Time.get_ticks_msec() / 1000.0
	
	print("[PlayerLogger] Session started: ", session_id)

## Stop logging and save to file
func end_session():
	if not enabled:
		return
	
	_save_log_file()
	enabled = false
	
	print("[PlayerLogger] Session ended. Logged ", log_data.size(), " frames. Saved to: ", current_log_file)

## Track a player for logging
func track_player(player: Node2D, player_id: String, username: String = ""):
	tracked_players[player_id] = {
		"player": player,
		"username": username if username != "" else player_id,
		"last_position": player.position,
		"last_velocity": Vector2.ZERO,
		"last_action": ActionType.IDLE,
		"frame_count": 0
	}
	
	print("[PlayerLogger] Now tracking player: ", username if username != "" else player_id)

## Untrack a player
func untrack_player(player_id: String):
	tracked_players.erase(player_id)

## Main update function - call from _process() or _physics_process()
func update(delta: float):
	if not enabled:
		return
	
	var current_time = Time.get_ticks_msec() / 1000.0
	
	if current_time - last_log_time < log_frequency:
		return
	
	last_log_time = current_time
	
	# Log data for all tracked players
	for player_id in tracked_players.keys():
		_log_player_frame(player_id, current_time, delta)

## Log a single frame for a player
func _log_player_frame(player_id: String, current_time: float, delta: float):
	var player_data = tracked_players[player_id]
	var player = player_data.player
	
	if not is_instance_valid(player):
		return
	
	# Calculate velocity
	var velocity = (player.position - player_data.last_position) / delta if delta > 0 else Vector2.ZERO
	
	# Detect action from velocity and inputs
	var action = _detect_action(player, velocity)
	
	# Get context data
	var context = _gather_context(player, current_time)
	
	# Create log entry
	var entry = {
		"time": current_time,
		"frame": player_data.frame_count,
		"player_id": player_id,
		"username": player_data.username,
		"position": {
			"x": player.position.x,
			"y": player.position.y
		},
		"tile": {
			"x": int(floor(player.position.x / Constants.TILE_SIZE)),
			"y": int(floor(player.position.y / Constants.TILE_SIZE))
		},
		"velocity": {
			"x": velocity.x,
			"y": velocity.y,
			"magnitude": velocity.length()
		},
		"action": ActionType.keys()[action],
		"context": context,
		"game_state": _get_game_state_snapshot()
	}
	
	log_data.append(entry)
	
	# Update tracking data
	player_data.last_position = player.position
	player_data.last_velocity = velocity
	player_data.last_action = action
	player_data.frame_count += 1

## Detect player action from state
func _detect_action(player: Node2D, velocity: Vector2) -> int:
	# Check if player died
	if player.has_method("is_dead") and player.is_dead:
		return ActionType.DIED
	
	# Check if bomb was placed (would need to track bomb count)
	if player.has_method("place_bomb_requested") and player.place_bomb_requested:
		return ActionType.PLACE_BOMB
	
	# Detect movement direction from velocity
	if velocity.length() > 10.0:  # Moving threshold
		# Determine primary direction
		if abs(velocity.x) > abs(velocity.y):
			if velocity.x > 0:
				return ActionType.MOVE_RIGHT
			else:
				return ActionType.MOVE_LEFT
		else:
			if velocity.y > 0:
				return ActionType.MOVE_DOWN
			else:
				return ActionType.MOVE_UP
	
	return ActionType.IDLE

## Gather contextual data around the player
func _gather_context(player: Node2D, current_time: float) -> Dictionary:
	var player_tile = Vector2i(
		int(floor(player.position.x / Constants.TILE_SIZE)),
		int(floor(player.position.y / Constants.TILE_SIZE))
	)
	
	var context = {
		"nearby_entities": [],
		"danger_level": 0.0,
		"time_until_explosion": INF,
		"escape_routes": 0,
		"nearest_powerup_distance": -1,
		"nearest_enemy_distance": -1,
		"bomb_count": 0,
		"can_place_bomb": false
	}
	
	# Get player stats
	if player.has_method("can_place_bomb"):
		context.can_place_bomb = player.can_place_bomb()
	
	if player.has_method("get") and player.get("bombs_placed") != null:
		context.bomb_count = player.bombs_placed
	
	# Danger analysis (if danger_mapper available)
	if danger_mapper != null:
		context.danger_level = danger_mapper.get_danger_at_tile(player_tile, current_time, 1.0)
		context.time_until_explosion = danger_mapper.get_time_until_explosion(player_tile, current_time)
	
	# Find nearby entities
	context.nearby_entities = _find_nearby_entities(player_tile, 5)  # 5 tile radius
	
	# Count escape routes (simple check)
	context.escape_routes = _count_walkable_neighbors(player_tile)
	
	# Find nearest powerup
	var nearest_powerup = _find_nearest_entity_of_type(player_tile, "powerup")
	if nearest_powerup != null:
		context.nearest_powerup_distance = nearest_powerup.distance
	
	# Find nearest enemy
	var nearest_enemy = _find_nearest_entity_of_type(player_tile, "player")
	if nearest_enemy != null:
		context.nearest_enemy_distance = nearest_enemy.distance
	
	return context

## Get snapshot of current game state
func _get_game_state_snapshot() -> Dictionary:
	if game_instance == null:
		return {}
	
	return {
		"players_alive": _count_alive_players(),
		"bombs_active": game_instance.bombs.size() if game_instance.has("bombs") else 0,
		"powerups_available": game_instance.powerups.size() if game_instance.has("powerups") else 0
	}

## Find entities near a tile
func _find_nearby_entities(center_tile: Vector2i, radius: int) -> Array:
	var entities = []
	
	if game_instance == null:
		return entities
	
	# Check bombs
	if game_instance.has("bombs"):
		for bomb_id in game_instance.bombs:
			var bomb = game_instance.bombs[bomb_id]
			if not is_instance_valid(bomb):
				continue
			
			var bomb_tile = bomb.get_tile_position()
			var distance = abs(bomb_tile.x - center_tile.x) + abs(bomb_tile.y - center_tile.y)
			
			if distance <= radius:
				entities.append({
					"type": "bomb",
					"distance": distance,
					"position": bomb.position
				})
	
	# Check soft blocks
	if game_instance.has("game_map"):
		for dy in range(-radius, radius + 1):
			for dx in range(-radius, radius + 1):
				var tile = center_tile + Vector2i(dx, dy)
				
				if tile.y < 0 or tile.y >= game_instance.game_map.size():
					continue
				if tile.x < 0 or tile.x >= game_instance.game_map[0].size():
					continue
				
				if game_instance.game_map[tile.y][tile.x] == 2:  # Soft block
					entities.append({
						"type": "soft_block",
						"distance": abs(dx) + abs(dy),
						"tile": tile
					})
	
	return entities

func _find_nearest_entity_of_type(center_tile: Vector2i, entity_type: String) -> Dictionary:
	var nearest = null
	var min_distance = INF
	
	if game_instance == null:
		return nearest
	
	match entity_type:
		"powerup":
			if game_instance.has("powerups"):
				for powerup_id in game_instance.powerups:
					var powerup = game_instance.powerups[powerup_id]
					if not is_instance_valid(powerup):
						continue
					
					var powerup_tile = powerup.get_tile_position()
					var distance = abs(powerup_tile.x - center_tile.x) + abs(powerup_tile.y - center_tile.y)
					
					if distance < min_distance:
						min_distance = distance
						nearest = {"distance": distance, "type": "powerup"}
		
		"player":
			if game_instance.has("players"):
				for player_id in game_instance.players:
					# Skip if this is the player we're logging
					if tracked_players.has(str(player_id)):
						continue
					
					var player = game_instance.players[player_id]
					if not is_instance_valid(player):
						continue
					
					var player_tile = player.get_tile_position()
					var distance = abs(player_tile.x - center_tile.x) + abs(player_tile.y - center_tile.y)
					
					if distance < min_distance:
						min_distance = distance
						nearest = {"distance": distance, "type": "player"}
	
	return nearest

func _count_walkable_neighbors(tile: Vector2i) -> int:
	if game_instance == null or not game_instance.has("game_map"):
		return 0
	
	var count = 0
	
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var neighbor = tile + dir
		
		if neighbor.y < 0 or neighbor.y >= game_instance.game_map.size():
			continue
		if neighbor.x < 0 or neighbor.x >= game_instance.game_map[0].size():
			continue
		
		var tile_type = game_instance.game_map[neighbor.y][neighbor.x]
		if tile_type == 0:  # Walkable
			count += 1
	
	return count

func _count_alive_players() -> int:
	if game_instance == null or not game_instance.has("players"):
		return 0
	
	var alive = 0
	for player_id in game_instance.players:
		var player = game_instance.players[player_id]
		if is_instance_valid(player):
			if not player.has_method("is_dead") or not player.is_dead:
				alive += 1
	
	return alive

## Save logged data to file
func _save_log_file():
	var file = FileAccess.open(current_log_file, FileAccess.WRITE)
	
	if file == null:
		push_error("[PlayerLogger] Failed to open log file: ", current_log_file)
		return
	
	var log_json = {
		"session_id": session_id,
		"timestamp": Time.get_datetime_string_from_system(),
		"total_frames": log_data.size(),
		"tracked_players": tracked_players.keys(),
		"data": log_data
	}
	
	file.store_string(JSON.stringify(log_json, "\t"))
	file.close()

## Export to CSV format (for ML training)
func export_to_csv(csv_filename: String = ""):
	if csv_filename == "":
		csv_filename = logs_directory + session_id + ".csv"
	
	var file = FileAccess.open(csv_filename, FileAccess.WRITE)
	
	if file == null:
		push_error("[PlayerLogger] Failed to open CSV file: ", csv_filename)
		return
	
	# Write header
	var header = "time,frame,player_id,pos_x,pos_y,tile_x,tile_y,vel_x,vel_y,vel_mag,action,danger,time_until_explosion,escape_routes,nearby_bombs,nearby_blocks,can_place_bomb\n"
	file.store_string(header)
	
	# Write data rows
	for entry in log_data:
		var row = "%f,%d,%s,%.2f,%.2f,%d,%d,%.2f,%.2f,%.2f,%s,%.2f,%.2f,%d,%d,%d,%s\n" % [
			entry.time,
			entry.frame,
			entry.player_id,
			entry.position.x,
			entry.position.y,
			entry.tile.x,
			entry.tile.y,
			entry.velocity.x,
			entry.velocity.y,
			entry.velocity.magnitude,
			entry.action,
			entry.context.danger_level,
			entry.context.time_until_explosion if entry.context.time_until_explosion != INF else 999.0,
			entry.context.escape_routes,
			_count_entities_of_type(entry.context.nearby_entities, "bomb"),
			_count_entities_of_type(entry.context.nearby_entities, "soft_block"),
			"1" if entry.context.can_place_bomb else "0"
		]
		file.store_string(row)
	
	file.close()
	print("[PlayerLogger] Exported to CSV: ", csv_filename)

func _count_entities_of_type(entities: Array, type: String) -> int:
	var count = 0
	for entity in entities:
		if entity.type == type:
			count += 1
	return count

## Utility: Generate unique session ID
func _generate_session_id() -> String:
	var time_dict = Time.get_datetime_dict_from_system()
	return "session_%04d%02d%02d_%02d%02d%02d" % [
		time_dict.year, time_dict.month, time_dict.day,
		time_dict.hour, time_dict.minute, time_dict.second
	]

## Log specific events (for reinforcement learning rewards)
func log_event(player_id: String, event_type: String, reward: float = 0.0, data: Dictionary = {}):
	if not enabled:
		return
	
	var event_entry = {
		"time": Time.get_ticks_msec() / 1000.0,
		"player_id": player_id,
		"event": event_type,
		"reward": reward,
		"data": data
	}
	
	log_data.append(event_entry)
	
	print("[PlayerLogger] Event logged: ", event_type, " (reward: ", reward, ")")
