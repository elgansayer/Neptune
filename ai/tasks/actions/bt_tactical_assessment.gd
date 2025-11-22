@tool
extends BTAction
class_name BTTacticalAssessment

## Evaluates the tactical situation and chooses the best attack strategy
## Implements advanced Bomberman tactics: trapping, space control, defensive positioning

@export var assessment_var: StringName = &"tactical_plan"  ## Stores chosen tactic in blackboard
@export var min_safety_margin: float = 1.5  ## Minimum time (seconds) to maintain safety

func _generate_name() -> String:
	return "TacticalAssessment → %s" % assessment_var

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var opponent_tracker = blackboard.get_var("opponent_tracker")
	var grid_sampler = blackboard.get_var("grid_sampler")
	var ai_manager = blackboard.get_var("ai_manager")
	var personality_config = blackboard.get_var("personality_config")
	
	if not player or not opponent_tracker or not grid_sampler or not ai_manager:
		return FAILURE
	
	var player_tile = player.get_tile_position()
	var nearest = opponent_tracker.get_nearest_opponent(player.position, player.peer_id)
	
	if nearest == null or nearest.is_empty():
		blackboard.set_var(assessment_var, "NONE")
		return FAILURE
	
	var opponent_tile: Vector2i = nearest.get("tile")
	var distance = grid_sampler.get_manhattan_distance(player_tile, opponent_tile)
	
	# Assess our current state
	var we_have_bombs = player.can_place_bomb()
	var our_range = player.bomb_range if player else 2
	var bomb_count = player.bombs_placed if player else 0
	var max_bombs = player.max_bombs if player else 10
	var trap_aggression = personality_config.get("trap_aggression", 0.5)
	
	# Assess threat matrix
	var threat_matrix = ai_manager.get_current_threat_matrix()
	var we_are_safe = not _is_in_danger(player_tile, threat_matrix)
	var opponent_is_safe = not _is_in_danger(opponent_tile, threat_matrix)
	
	# Count available escape routes for opponent
	var opponent_escape_routes = _count_escape_routes(opponent_tile, grid_sampler, ai_manager)
	
	# === TACTICAL DECISION TREE ===
	
	var chosen_tactic = "NONE"
	var priority = 0
	
	# PRIORITY 1: One-Tile Trap (The Kiss) - opponent has 1 escape route
	if opponent_escape_routes == 1 and we_have_bombs and distance <= 4:
		chosen_tactic = "ONE_TILE_TRAP"
		priority = 10
		print("[TacticalAssessment] 🎯 ONE-TILE TRAP: Opponent cornered with 1 exit!")
	
	# PRIORITY 2: Choke Point Trap - opponent has 2 escape routes, we can block one
	elif opponent_escape_routes == 2 and we_have_bombs and distance <= 5 and trap_aggression > 0.6:
		chosen_tactic = "CHOKE_POINT"
		priority = 9
		print("[TacticalAssessment] 🕷️ CHOKE POINT: Opponent has limited exits")
	
	# PRIORITY 3: Space Denial - opponent moving toward us, we have range advantage
	elif distance <= our_range + 2 and we_have_bombs and we_are_safe:
		chosen_tactic = "SPACE_DENIAL"
		priority = 8
		print("[TacticalAssessment] 🚫 SPACE DENIAL: Cut off opponent's movement")
	
	# PRIORITY 4: Aggressive Chase - we have bomb advantage
	elif (max_bombs - bomb_count) >= 3 and distance <= 8 and we_are_safe:
		chosen_tactic = "AGGRESSIVE_CHASE"
		priority = 7
		print("[TacticalAssessment] 🏃 AGGRESSIVE CHASE: Bomb advantage, press attack")
	
	# PRIORITY 5: Defensive Positioning - we're in danger, need to escape first
	elif not we_are_safe:
		chosen_tactic = "DEFENSIVE_RETREAT"
		priority = 10  # Highest priority - survival!
		print("[TacticalAssessment] 🛡️ DEFENSIVE RETREAT: We're in danger!")
	
	# PRIORITY 6: Patient Ambush - opponent is in danger, let them die
	elif not opponent_is_safe and distance > 3:
		chosen_tactic = "WAIT_FOR_DEATH"
		priority = 6
		print("[TacticalAssessment] ⏰ WAIT: Opponent trapped, stay safe")
	
	# PRIORITY 7: Predictive Intercept - standard chase
	elif distance <= 12 and we_have_bombs:
		chosen_tactic = "PREDICTIVE_INTERCEPT"
		priority = 5
		print("[TacticalAssessment] 🎯 INTERCEPT: Standard pursuit")
	
	# DEFAULT: No good tactic available
	else:
		chosen_tactic = "NONE"
		priority = 0
	
	# Store assessment in blackboard
	blackboard.set_var(assessment_var, chosen_tactic)
	blackboard.set_var("tactical_priority", priority)
	blackboard.set_var("opponent_escape_routes", opponent_escape_routes)
	blackboard.set_var("opponent_distance", distance)
	
	return SUCCESS if chosen_tactic != "NONE" else FAILURE

func _is_in_danger(tile: Vector2i, threat_matrix: Dictionary) -> bool:
	var key = "%d,%d" % [tile.x, tile.y]
	return threat_matrix.has(key)

func _count_escape_routes(tile: Vector2i, grid_sampler, ai_manager) -> int:
	"""Count number of safe adjacent tiles opponent can move to"""
	var safe_routes = 0
	var threat_matrix = ai_manager.get_current_threat_matrix()
	
	for dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
		var check_tile = tile + dir
		
		# Must be walkable
		if not grid_sampler.is_tile_walkable(check_tile):
			continue
		
		# Must not be in danger
		var key = "%d,%d" % [check_tile.x, check_tile.y]
		if threat_matrix.has(key):
			continue
		
		safe_routes += 1
	
	return safe_routes
