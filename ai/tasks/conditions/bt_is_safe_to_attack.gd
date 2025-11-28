@tool
extends BTCondition
class_name BTIsSafeToAttack

## Validates that attacking won't trap the bot
## Checks escape routes and safety margins before committing to offensive action
## Includes HYSTERESIS to prevent flickering

@export var min_escape_routes: int = 1 ## Minimum safe exits required
@export var safety_time_margin: float = 1.5 ## Minimum seconds to reach safety

func _generate_name() -> String:
	return "IsSafeToAttack (routes≥%d, margin≥%.1fs)" % [min_escape_routes, safety_time_margin]

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var grid_sampler = blackboard.get_var("grid_sampler")
	var ai_manager = blackboard.get_var("ai_manager")
	var bomb_safety_checker = blackboard.get_var("bomb_safety_checker")
	var personality_config = blackboard.get_var("personality_config")
	
	if not player or not grid_sampler or not ai_manager or not bomb_safety_checker:
		return FAILURE
	
	var player_tile = player.get_tile_position()
	var current_time_msec = Time.get_ticks_msec()
	
	# CRITICAL: If we are currently in danger (or latched), we CANNOT attack
	# This prevents oscillation where we stop escaping to attack because IsSafeToAttack says "Safe"
	if blackboard.get_var("in_danger", false):
		# print("[IsSafeToAttack] ✗ UNSAFE: Currently in DANGER state (latched or immediate)")
		blackboard.set_var("was_safe_to_attack", false)
		return FAILURE
	
	# Adjust safety requirements based on personality
	var personality = blackboard.get_var("personality", "BALANCED")
	var adjusted_margin = safety_time_margin
	
	match personality:
		"COMPETITIVE":
			adjusted_margin = 0.4 # Highly aggressive - take risks!
		"KAMIKAZE":
			adjusted_margin = 0.3 # Very risky
		"AGGRESSIVE":
			adjusted_margin = 0.8 # Risky
		"BALANCED":
			adjusted_margin = 1.5 # Standard
		"STRATEGIC":
			adjusted_margin = 1.8 # Cautious
		"DEFENSIVE", "TIMID":
			adjusted_margin = 2.5 # Very cautious
	
	# Hysteresis: If we were safe to attack previously, be more lenient to stay in that state
	# This prevents flickering when on the edge of safety
	var was_safe = false
	if blackboard.has_var("was_safe_to_attack"):
		was_safe = blackboard.get_var("was_safe_to_attack")
	
	var effective_margin = adjusted_margin
	var effective_routes = min_escape_routes
	
	if was_safe:
		# SIGNIFICANTLY more lenient if we are already committed
		# This is the "Latch" logic
		effective_margin *= 0.6 # 40% reduction in required margin
		effective_routes = max(1, min_escape_routes - 1) # Allow 1 fewer route (but at least 1)
	
	# Check if we can safely place a bomb here
	var bomb_range = player.bomb_range if player else 2
	var bot_speed = 5.0 # tiles per second
	
	var safety_check = bomb_safety_checker.check_plant_safety_detailed(
		player_tile,
		player_tile,
		bomb_range,
		bot_speed,
		current_time_msec
	)
	
	if not safety_check.get("safe", false):
		var margin_ms = safety_check.get("margin_ms", 0.0)
		var margin_sec = margin_ms / 1000.0
		
		if margin_sec < effective_margin * 1000.0:
			# print("[IsSafeToAttack] ✗ UNSAFE: Escape margin too small (", margin_sec, "s < ", effective_margin, "s)")
			blackboard.set_var("was_safe_to_attack", false)
			return FAILURE
	
	# Count current escape routes
	var escape_routes = _count_escape_routes(player_tile, grid_sampler, ai_manager)
	
	# CRITICAL: If in a dead end (1 or fewer exits), we CANNOT attack!
	# We must move out first before attempting any offensive action.
	# This prevents the DEAD-END ABORT spam in bt_place_bomb.
	if escape_routes <= 1:
		# print("[IsSafeToAttack] ✗ UNSAFE: Dead end position (only %d exits) - move out first!" % escape_routes)
		blackboard.set_var("was_safe_to_attack", false)
		blackboard.set_var("in_dead_end", true)  # Signal to other tasks
		return FAILURE
	else:
		blackboard.set_var("in_dead_end", false)
	
	if escape_routes < effective_routes:
		# print("[IsSafeToAttack] ✗ UNSAFE: Not enough escape routes (", escape_routes, " < ", effective_routes, ")")
		blackboard.set_var("was_safe_to_attack", false)
		return FAILURE
	
	# Check if we're already in a dangerous situation
	var threat_matrix = ai_manager.get_current_threat_matrix()
	var key = "%d,%d" % [player_tile.x, player_tile.y]
	
	if threat_matrix.has(key):
		# print("[IsSafeToAttack] ✗ UNSAFE: Currently in danger zone")
		blackboard.set_var("was_safe_to_attack", false)
		return FAILURE
	
	# print("[IsSafeToAttack] ✓ SAFE: ", escape_routes, " exits, margin OK")
	blackboard.set_var("was_safe_to_attack", true)
	return SUCCESS

func _count_escape_routes(tile: Vector2i, grid_sampler, ai_manager) -> int:
	"""Count number of safe adjacent tiles we can escape to"""
	var safe_routes = 0
	var threat_matrix = ai_manager.get_current_threat_matrix()
	
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var check_tile = tile + dir
		
		# Must be walkable
		if not grid_sampler.is_tile_walkable(check_tile):
			continue
		
		# Must not be in current danger
		var key = "%d,%d" % [check_tile.x, check_tile.y]
		if threat_matrix.has(key):
			continue
		
		safe_routes += 1
	
	return safe_routes
