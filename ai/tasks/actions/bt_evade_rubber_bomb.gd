@tool
extends BTAction
class_name BTEvadeRubberBomb

## Specialized evasion for kicked/rubber bombs
## Tracks bomb trajectory and moves perpendicular to avoid getting hit
## More urgent than normal bomb threats since kicked bombs move fast

@export var target_tile_var: StringName = &"evade_cell"  ## Blackboard variable to store evasion target
@export var detection_radius: int = 8  ## How far to detect kicked bombs (tiles)
@export var urgency_threshold: float = 2.0  ## Consider urgent if bomb within this many seconds

func _generate_name() -> String:
	return "EvadeRubberBomb → %s" % target_tile_var

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var game_instance = blackboard.get_var("game_instance")
	var grid_sampler = blackboard.get_var("grid_sampler")
	var ai_manager = blackboard.get_var("ai_manager")
	
	if not player or not game_instance or not grid_sampler or not ai_manager:
		return FAILURE
	
	var player_tile = player.get_tile_position()
	var player_pos = player.position
	
	# Scan for kicked bombs nearby
	var nearest_kicked_bomb = null
	var nearest_distance := INF
	
	for bomb_id in game_instance.bombs:
		var bomb = game_instance.bombs[bomb_id]
		if not is_instance_valid(bomb):
			continue
		
		# Check if bomb is kicked (moving)
		if bomb.get("bomb_state") != 3:  # BombState.KICKED = 3
			continue
		
		var bomb_tile = bomb.get_tile_position()
		var distance = grid_sampler.get_manhattan_distance(player_tile, bomb_tile)
		
		if distance < nearest_distance and distance <= detection_radius:
			nearest_distance = distance
			nearest_kicked_bomb = bomb
	
	# No kicked bombs nearby
	if nearest_kicked_bomb == null:
		return FAILURE
	
	var bomb_pos = nearest_kicked_bomb.position
	var bomb_velocity: Vector2 = nearest_kicked_bomb.get("kick_direction") * nearest_kicked_bomb.get("kick_speed")
	
	# Calculate if we're in the bomb's path
	var bomb_to_player = player_pos - bomb_pos
	var bomb_direction = bomb_velocity.normalized()
	
	# Project player position onto bomb's trajectory
	var projection = bomb_to_player.dot(bomb_direction)
	
	# Check if we're in front of the bomb (positive projection)
	if projection <= 0:
		# Bomb is moving away or not toward us
		return FAILURE
	
	# Calculate perpendicular distance from trajectory
	var perpendicular_dist = abs(bomb_to_player.cross(bomb_direction))
	var tile_size = GameConfig.TILE_SIZE
	
	# If we're in the trajectory path (within 1 tile width)
	if perpendicular_dist < tile_size * 1.5:
		# URGENT: We're directly in the bomb's path!
		print("[BTEvadeRubberBomb] ⚠️ URGENT! Kicked bomb heading toward us!")
		
		# Calculate time until impact
		var time_to_impact = projection / bomb_velocity.length()
		
		if time_to_impact < urgency_threshold:
			# Find perpendicular escape route
			var escape_tile = _find_perpendicular_escape(
				player_tile,
				bomb_direction,
				grid_sampler,
				ai_manager
			)
			
			if escape_tile != Vector2i.ZERO:
				blackboard.set_var(target_tile_var, escape_tile)
				blackboard.set_var("evade_bomb_id", nearest_kicked_bomb.bomb_id)
				blackboard.set_var("evade_urgency", "HIGH")
				return SUCCESS
	
	# We detected a kicked bomb but not in immediate danger
	# Still try to stay clear of its path
	var safe_tile = _find_safe_distance(
		player_tile,
		nearest_kicked_bomb.get_tile_position(),
		bomb_velocity,
		grid_sampler,
		ai_manager
	)
	
	if safe_tile != Vector2i.ZERO and safe_tile != player_tile:
		blackboard.set_var(target_tile_var, safe_tile)
		blackboard.set_var("evade_bomb_id", nearest_kicked_bomb.bomb_id)
		blackboard.set_var("evade_urgency", "MEDIUM")
		return SUCCESS
	
	return FAILURE

## Find tile perpendicular to bomb's trajectory
func _find_perpendicular_escape(
	player_tile: Vector2i,
	bomb_direction: Vector2,
	grid_sampler,
	ai_manager
) -> Vector2i:
	# Get perpendicular vectors (left and right)
	var perpendicular_left = Vector2(-bomb_direction.y, bomb_direction.x).normalized()
	var perpendicular_right = Vector2(bomb_direction.y, -bomb_direction.x).normalized()
	
	# Try both perpendicular directions
	var candidates: Array[Vector2i] = []
	
	for perp_dir in [perpendicular_left, perpendicular_right]:
		# Convert to tile direction
		var tile_dir: Vector2i
		if abs(perp_dir.x) > abs(perp_dir.y):
			tile_dir = Vector2i(sign(perp_dir.x), 0)
		else:
			tile_dir = Vector2i(0, sign(perp_dir.y))
		
		# Check 1-2 tiles in that direction
		for distance in [1, 2]:
			var check_tile = player_tile + (tile_dir * distance)
			
			if not grid_sampler.is_tile_walkable(check_tile):
				continue
			
			# Check if safe from other threats
			var key = "%d,%d" % [check_tile.x, check_tile.y]
			if ai_manager.get_current_threat_matrix().has(key):
				continue
			
			candidates.append(check_tile)
	
	# Return nearest safe perpendicular tile
	if candidates.size() > 0:
		return candidates[0]
	
	# Fallback: just move away from current position
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var fallback = player_tile + dir
		if grid_sampler.is_tile_walkable(fallback):
			return fallback
	
	return Vector2i.ZERO

## Find tile at safe distance from kicked bomb's trajectory
func _find_safe_distance(
	player_tile: Vector2i,
	bomb_tile: Vector2i,
	bomb_velocity: Vector2,
	grid_sampler,
	ai_manager
) -> Vector2i:
	# Calculate bomb's projected path (next few tiles)
	var bomb_path: Array[Vector2i] = []
	var current = bomb_tile
	var direction = bomb_velocity.normalized()
	
	for i in range(6):  # Project 6 tiles ahead
		var next: Vector2i
		if abs(direction.x) > abs(direction.y):
			next = current + Vector2i(sign(direction.x), 0)
		else:
			next = current + Vector2i(0, sign(direction.y))
		
		if not grid_sampler.is_tile_walkable(next):
			break
		
		bomb_path.append(next)
		current = next
	
	# Find tiles that are NOT in the bomb's path and are adjacent to us
	var safe_tiles: Array[Vector2i] = []
	
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var check_tile = player_tile + dir
		
		if not grid_sampler.is_tile_walkable(check_tile):
			continue
		
		# Skip if in bomb path
		if check_tile in bomb_path:
			continue
		
		# Skip if in threat matrix
		var key = "%d,%d" % [check_tile.x, check_tile.y]
		if ai_manager.get_current_threat_matrix().has(key):
			continue
		
		safe_tiles.append(check_tile)
	
	# Return closest safe tile
	if safe_tiles.size() > 0:
		return safe_tiles[0]
	
	return Vector2i.ZERO
