@tool
extends BTCondition
class_name BTIsInDanger

## Checks if the entity is currently in danger from explosions
## Uses the HazardPredictor to determine if current tile is dangerous

@export var danger_buffer: float = 1.0  ## Safety margin (seconds) before danger becomes lethal
@export var check_immediate: bool = true  ## Check only immediate danger (no buffer)
@export var evaluate_all_threats: bool = true ## If true, returns SUCCESS if ANY threat exists on tile (regardless of time)
@export var debug_logging: bool = true

func _generate_name() -> String:
	return "IsInDanger"

func _tick(delta: float) -> int:
	var player = blackboard.get_var("player")
	var hazard_predictor = blackboard.get_var("hazard_predictor")
	
	if not player or not hazard_predictor:
		push_warning("[BTIsInDanger] Missing required blackboard variables: player or hazard_predictor")
		return FAILURE
	
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
