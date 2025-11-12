extends Node
class_name BombThrowPredictor

# Client-side prediction for Power Glove bomb throwing
# Provides immediate visual feedback while waiting for server confirmation

const THROW_RANGE: int = 3  # Must match ServerBomb.THROW_RANGE
const THROW_DURATION: float = 0.6  # Must match ServerBomb.THROW_DURATION
const THROW_HEIGHT: float = 100.0  # Must match ServerBomb.THROW_HEIGHT

# Prediction state
var predicted_throws := {}  # bomb_id -> prediction data

# Correction parameters
const CORRECTION_SPEED := 10.0  # How fast to lerp to server position
const DESYNC_THRESHOLD := 5.0  # Pixels - when to apply correction

func predict_throw(bomb_id: String, start_pos: Vector2, throw_direction: Vector2, 
				  game_map: Array) -> Dictionary:
	"""
	Predict bomb throw trajectory for immediate client feedback.
	Returns prediction data including target position and timing.
	"""
	var prediction = {
		"bomb_id": bomb_id,
		"start_pos": start_pos,
		"throw_direction": throw_direction.normalized(),
		"start_time": Time.get_ticks_msec() / 1000.0,
		"duration": THROW_DURATION,
		"target_pos": Vector2.ZERO,
		"is_active": true,
		"server_confirmed": false
	}
	
	# Calculate predicted landing position
	prediction["target_pos"] = _calculate_predicted_target(
		start_pos, 
		throw_direction, 
		game_map
	)
	
	predicted_throws[bomb_id] = prediction
	return prediction

func _calculate_predicted_target(start_pos: Vector2, direction: Vector2, 
								game_map: Array) -> Vector2:
	"""Calculate predicted landing position (client-side, may differ from server)"""
	var start_tile = Vector2i(
		int(floor(start_pos.x / GameConfig.TILE_SIZE)),
		int(floor(start_pos.y / GameConfig.TILE_SIZE))
	)
	
	var current_tile = start_tile
	var remaining_distance = THROW_RANGE
	
	while remaining_distance > 0:
		var next_tile = current_tile + Vector2i(
			int(direction.x),
			int(direction.y)
		)
		
		# Check if tile is blocked (simplified client-side check)
		if _is_tile_blocked(next_tile, game_map):
			break
		
		current_tile = next_tile
		remaining_distance -= 1
	
	# Return world position at tile center
	return Vector2(
		current_tile.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
		current_tile.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
	)

func _is_tile_blocked(tile: Vector2i, game_map: Array) -> bool:
	"""Simple client-side tile blocking check"""
	if tile.y < 0 or tile.y >= game_map.size():
		return true
	if tile.x < 0 or tile.x >= game_map[0].size():
		return true
	
	var tile_type = game_map[tile.y][tile.x]
	return tile_type != 0  # 0 = empty, 1 = wall, 2 = block

func get_predicted_position(bomb_id: String, current_time: float) -> Dictionary:
	"""
	Get the predicted position of a thrown bomb at current time.
	Returns: {position: Vector2, z_height: float, progress: float}
	"""
	if not predicted_throws.has(bomb_id):
		return {"position": Vector2.ZERO, "z_height": 0.0, "progress": 1.0}
	
	var prediction = predicted_throws[bomb_id]
	var elapsed = current_time - prediction["start_time"]
	var progress = clampf(elapsed / prediction["duration"], 0.0, 1.0)
	
	# Calculate position along arc
	var pos = prediction["start_pos"].lerp(prediction["target_pos"], progress)
	
	# Calculate pseudo-3D height (parabolic arc)
	var height_progress = 1.0 - abs(progress * 2.0 - 1.0)  # Peak at 0.5
	var z_height = THROW_HEIGHT * height_progress
	
	return {
		"position": pos,
		"z_height": z_height,
		"progress": progress
	}

func confirm_server_throw(bomb_id: String, server_start: Vector2, server_target: Vector2):
	"""
	Server confirmed the throw with authoritative trajectory.
	Check if we need to correct our prediction.
	"""
	if not predicted_throws.has(bomb_id):
		# We didn't predict this throw, create entry
		predicted_throws[bomb_id] = {
			"bomb_id": bomb_id,
			"start_pos": server_start,
			"target_pos": server_target,
			"start_time": Time.get_ticks_msec() / 1000.0,
			"duration": THROW_DURATION,
			"is_active": true,
			"server_confirmed": true
		}
		return
	
	var prediction = predicted_throws[bomb_id]
	
	# Check if our prediction differs significantly from server
	var target_diff = prediction["target_pos"].distance_to(server_target)
	
	if target_diff > DESYNC_THRESHOLD:
		print("[BombThrowPredictor] Correcting prediction for ", bomb_id, 
			  " - diff: ", target_diff, "px")
		
		# Update to server's authoritative trajectory
		prediction["target_pos"] = server_target
		prediction["start_pos"] = server_start
	
	prediction["server_confirmed"] = true

func apply_correction(bomb_id: String, server_pos: Vector2, delta: float) -> Vector2:
	"""
	Smoothly correct predicted position toward server position.
	Returns the corrected position.
	"""
	if not predicted_throws.has(bomb_id):
		return server_pos
	
	var prediction = predicted_throws[bomb_id]
	var current_time = Time.get_ticks_msec() / 1000.0
	var predicted = get_predicted_position(bomb_id, current_time)
	
	var distance = predicted["position"].distance_to(server_pos)
	
	if distance > DESYNC_THRESHOLD:
		# Smoothly lerp toward server position
		return predicted["position"].lerp(server_pos, CORRECTION_SPEED * delta)
	else:
		# Close enough - use predicted position for smooth visuals
		return predicted["position"]

func cleanup_prediction(bomb_id: String):
	"""Remove prediction data when bomb lands or explodes"""
	if predicted_throws.has(bomb_id):
		predicted_throws.erase(bomb_id)

func clear_all_predictions():
	"""Clear all prediction data (e.g., on disconnect)"""
	predicted_throws.clear()
