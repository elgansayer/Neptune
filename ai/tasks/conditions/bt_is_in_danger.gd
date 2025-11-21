@tool
extends BTCondition
class_name BTIsInDanger

## Checks if the entity is currently in danger from explosions
## Uses the HazardPredictor to determine if current tile is dangerous

@export var danger_buffer: float = 1.0 ## Safety margin (seconds) before danger becomes lethal
@export var check_immediate: bool = true ## Check only immediate danger (no buffer)
@export var evaluate_all_threats: bool = true ## If true, returns SUCCESS if ANY threat exists on tile (regardless of time)
@export var debug_logging: bool = true

func _generate_name() -> String:
	return "IsInDanger"

func _tick(delta: float) -> int:
	var player = blackboard.get_var("player")
	var hazard_predictor = blackboard.get_var("hazard_predictor")
	var grid_sampler = blackboard.get_var("grid_sampler")
	
	if not player or not hazard_predictor:
		push_warning("[BTIsInDanger] Missing required blackboard variables: player or hazard_predictor")
		return FAILURE
	
	# DEBUG: Unconditional log to verify execution
	print("[BTIsInDanger] _tick called. Tile: ", player.get_tile_position())
	
	# if Engine.get_physics_frames() % 60 == 0:
	# 	print("[BTIsInDanger] TICK - player_tile=%s" % player.get_tile_position())
	
	var player_tile = player.get_tile_position()
	var current_time = Time.get_ticks_msec() / 1000.0
	
	# is_tile_safe returns true if safe, so we need to invert for danger check
	var is_safe: bool
	
	if evaluate_all_threats:
		# Strict mode: Any threat is dangerous
		is_safe = not hazard_predictor.is_tile_threatened(player_tile)
	elif check_immediate:
		is_safe = hazard_predictor.is_tile_safe(player_tile, current_time, 0.0)
	else:
		is_safe = hazard_predictor.is_tile_safe(player_tile, current_time, danger_buffer)
	
	var is_dangerous = not is_safe
	
	if is_dangerous:
		# Store danger info in blackboard for potential use by other nodes
		blackboard.set_var("in_danger", true)
		blackboard.set_var("danger_tile", player_tile)
		_debug("Danger detected at %s (buffer=%s)" % [player_tile, danger_buffer if not check_immediate else 0.0])
		return SUCCESS
	else:
		blackboard.set_var("in_danger", false)
		_debug("Tile %s safe" % player_tile)
		return FAILURE

func _debug(message: String) -> void:
	if debug_logging:
		print("[BTIsInDanger] ", message)

func _get_blast_tiles(center: Vector2i, range_val: int, grid_sampler) -> Array[Vector2i]:
	"""Calculate which tiles will be hit by bomb explosion (respecting walls)"""
	var tiles: Array[Vector2i] = [center]
	
	if not grid_sampler:
		return tiles
	
	# Check four cardinal directions
	var directions := [Vector2i.RIGHT, Vector2i.LEFT, Vector2i.UP, Vector2i.DOWN]
	
	for dir: Vector2i in directions:
		for dist in range(1, range_val + 1):
			var tile: Vector2i = center + (dir * dist)
			
			# Check if walkable (walls block explosions)
			if not grid_sampler.is_tile_walkable(tile):
				var tile_type = grid_sampler.get_tile_type(tile)
				if tile_type == 1: # Hard wall - stop blast
					break
				elif tile_type == 2: # Soft block - blast hits it but stops
					tiles.append(tile)
					break
			else:
				# Empty tile - blast continues
				tiles.append(tile)
	
	return tiles
