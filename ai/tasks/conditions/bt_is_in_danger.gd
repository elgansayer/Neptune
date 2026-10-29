@tool
extends BTCondition
class_name BTIsInDanger

const SimulationTime = preload("res://shared/ai/simulation_time.gd")

## Checks if the entity is currently in danger from explosions
## Uses the HazardPredictor to determine if current tile is dangerous

@export var danger_buffer: float = 1.0 ## Safety margin (seconds) before danger becomes lethal
@export var check_immediate: bool = true ## Check only immediate danger (no buffer)
@export var evaluate_all_threats: bool = true ## If true, returns SUCCESS if ANY threat exists on tile (regardless of time)
@export var debug_logging: bool = false

static var _tick_count: int = 0

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
	# print("[BTIsInDanger] _tick called. Tile: ", player.get_tile_position())
	
	# if Engine.get_physics_frames() % 60 == 0:
	# 	print("[BTIsInDanger] TICK - player_tile=%s" % player.get_tile_position())
	
	var player_tile = player.get_tile_position()
	var current_time = SimulationTime.seconds(blackboard)
	
	# CRITICAL: Check if bot is standing on a bomb - IMMEDIATE DANGER!
	var game_instance = blackboard.get_var("game_instance")
	if game_instance and "bombs" in game_instance:
		for bomb_id in game_instance.bombs:
			var bomb = game_instance.bombs[bomb_id]
			if is_instance_valid(bomb) and not bomb.has_exploded:
				if bomb.get_tile_position() == player_tile:
					# Standing on a bomb! Immediate danger!
					blackboard.set_var("in_danger", true)
					blackboard.set_var("was_in_danger", true)
					blackboard.set_var("danger_tile", player_tile)
					print("[BTIsInDanger] ⚠️ CRITICAL: Bot standing on bomb at ", player_tile, "!")
					return SUCCESS
	
	# is_tile_safe returns true if safe, so we need to invert for danger check
	var is_safe: bool
	var is_dangerous: bool # Declare here to ensure scope for print and subsequent checks
	
	if evaluate_all_threats:
		# Strict mode: Any threat is dangerous
		# Assuming 'bomb_safety_checker' is meant to be 'hazard_predictor'
		# and 'is_tile_dangerous' is the inverse of 'is_tile_threatened'
		is_dangerous = hazard_predictor.is_tile_threatened(player_tile)
	elif check_immediate:
		is_safe = hazard_predictor.is_tile_safe(player_tile, current_time, 0.0)
		is_dangerous = not is_safe
	else:
		is_safe = hazard_predictor.is_tile_safe(player_tile, current_time, danger_buffer)
		is_dangerous = not is_safe
	
	# print("[BTIsInDanger] is_dangerous=", is_dangerous, " at ", player_tile)
	
	# The original code had `var is_dangerous = not is_safe` here.
	# With the new logic for `evaluate_all_threats`, `is_dangerous` is already set.
	# We need to ensure `is_dangerous` is always set before the print statement.
	# The previous block now correctly sets `is_dangerous` based on the conditions.
	
	# Hysteresis: Once in danger, require lower threshold (50%) to exit danger state
	# This prevents flickering between danger/safe that causes behavior tree restarts
	var was_in_danger = false
	if blackboard.has_var("was_in_danger"):
		was_in_danger = blackboard.get_var("was_in_danger")
	
	if was_in_danger and not is_dangerous:
		# We were in danger, check if we're SIGNIFICANTLY safer now
		# Re-check with reduced buffer (50% of original)
		var reduced_buffer = danger_buffer * 0.5
		var still_risky = not hazard_predictor.is_tile_safe(player_tile, current_time, reduced_buffer)
		if still_risky:
			is_dangerous = true # Stay in danger state
	
	# ESCAPE COMMITMENT:
	# If we are in the middle of an escape (was_in_danger + escape_route_found),
	# we MUST NOT exit danger state until we reach the safe target.
	# This prevents the bot from stepping onto a "temporarily safe" tile, thinking it's safe,
	# switching to farming, and then turning back into danger.
	if not is_dangerous and was_in_danger:
		var escape_route_found = blackboard.get_var("escape_route_found", false)
		if escape_route_found:
			# CRITICAL FIX: Use "escape_cell" as primary, fallback to "target_cell"
			# The behavior tree uses "escape_cell" for the escape action!
			var target_cell = blackboard.get_var("escape_cell") if blackboard.has_var("escape_cell") else null
			if target_cell == null:
				target_cell = blackboard.get_var("target_cell") if blackboard.has_var("target_cell") else null
				
			if target_cell != null and target_cell is Vector2i:
				# We have an active escape target. Are we there yet?
				if player_tile != target_cell:
					is_dangerous = true
					_debug("maintaining danger state for ESCAPE COMMITMENT (target=%s)" % target_cell)
	
	if is_dangerous:
		# Store danger info in blackboard for potential use by other nodes
		blackboard.set_var("in_danger", true)
		blackboard.set_var("was_in_danger", true) # Update hysteresis state
		blackboard.set_var("danger_tile", player_tile)
		_debug("Danger detected at %s (buffer=%s)" % [player_tile, danger_buffer if not check_immediate else 0.0])
		return SUCCESS
	else:
		blackboard.set_var("in_danger", false)
		blackboard.set_var("was_in_danger", false) # Update hysteresis state
		
		# CRITICAL: Clear escape route flag when we're safe
		# Otherwise bots stay in danger mode forever!
		if blackboard.get_var("escape_route_found", false):
			blackboard.set_var("escape_route_found", false)
			blackboard.set_var("escape_cell", null)
		
		# Debug why it thinks it's safe
		if debug_logging:
			print("[BTIsInDanger] FAILURE: Tile %s considered SAFE. evaluate_all_threats=%s, is_tile_threatened=%s" % [
				player_tile, evaluate_all_threats, hazard_predictor.is_tile_threatened(player_tile)
			])
		
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
