@tool
extends BTAction
class_name BTTacticalAssessment

## Evaluates the tactical situation and chooses the best attack strategy
## Implements advanced Bomberman tactics: trapping, space control, defensive positioning
## Includes HYSTERESIS to prevent rapid switching between tactics

@export var assessment_var: StringName = &"tactical_plan" ## Stores chosen tactic in blackboard
@export var min_safety_margin: float = 1.5 ## Minimum time (seconds) to maintain safety
@export var lock_duration_ms: int = 1000 ## Minimum time to stick to a tactic (unless critical)

# Hysteresis state
var _current_tactic: String = "NONE"
var _tactic_start_time: int = 0
var _last_opponent_pos: Vector2i = Vector2i(-999, -999)

func _generate_name() -> String:
	return "TacticalAssessment → %s" % assessment_var

func _enter() -> void:
	# Don't reset state here! We want persistence across ticks
	pass

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
		_set_tactic("NONE", 0)
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
	
	var new_tactic = "NONE"
	var new_priority = 0
	
	# PRIORITY 1: One-Tile Trap (The Kiss) - opponent has 1 escape route
	if opponent_escape_routes == 1 and we_have_bombs and distance <= 4:
		new_tactic = "ONE_TILE_TRAP"
		new_priority = 10
	
	# PRIORITY 2: Choke Point Trap - opponent has 2 escape routes, we can block one
	elif opponent_escape_routes == 2 and we_have_bombs and distance <= 5 and trap_aggression > 0.5:
		new_tactic = "CHOKE_POINT"
		new_priority = 9
	
	# PRIORITY 2.5: Setup Trap - opponent has 3 escape routes, proactively block one to create choke
	# This is the KEY to strategic Bomberman - start limiting options BEFORE they're cornered
	elif opponent_escape_routes == 3 and we_have_bombs and distance <= 6 and trap_aggression > 0.4:
		new_tactic = "CHOKE_POINT" # Use same execution, but start earlier
		new_priority = 8
	
	# PRIORITY 3: Space Denial - opponent moving toward us or we're close, cut off movement
	elif distance <= our_range + 2 and we_have_bombs and we_are_safe:
		new_tactic = "SPACE_DENIAL"
		new_priority = 7
	
	# PRIORITY 4: Aggressive Chase - we have bomb advantage
	elif (max_bombs - bomb_count) >= 2 and distance <= 8 and we_are_safe:
		new_tactic = "AGGRESSIVE_CHASE"
		new_priority = 6
	
	# PRIORITY 5: Defensive Positioning - we're in danger, need to escape first
	# NOTE: Usually handled by higher level "Escape" node, but good as fallback
	elif not we_are_safe:
		new_tactic = "DEFENSIVE_RETREAT"
		new_priority = 100 # CRITICAL priority - override everything
	
	# PRIORITY 6: Patient Ambush - opponent is in danger, let them die
	elif not opponent_is_safe and distance > 2:
		new_tactic = "WAIT_FOR_DEATH"
		new_priority = 5
	
	# PRIORITY 7: Predictive Intercept - standard chase
	elif distance <= 12 and we_have_bombs:
		new_tactic = "PREDICTIVE_INTERCEPT"
		new_priority = 4
	
	# DEFAULT: No good tactic available
	else:
		new_tactic = "NONE"
		new_priority = 0
	
	# === HYSTERESIS & LOCKING ===
	var current_time = Time.get_ticks_msec()
	var time_since_switch = current_time - _tactic_start_time
	
	# Determine if we should switch
	var should_switch = false
	
	# 1. Critical override (Danger)
	if new_priority >= 100:
		should_switch = true
		
	# 2. Current tactic became invalid (NONE)
	elif _current_tactic == "NONE" or new_tactic == "NONE":
		should_switch = true # Always allow switching to/from NONE to avoid getting stuck doing nothing
		
	# 3. Lock expired AND new tactic is better or different
	elif time_since_switch > lock_duration_ms:
		if new_tactic != _current_tactic:
			# Only switch if priority is higher or equal (prevent downgrading unless necessary)
			# Or if the old tactic is no longer applicable (logic above handles that implicitly via if/else chain)
			should_switch = true
			
	# 4. New tactic is SIGNIFICANTLY better (Priority Jump)
	# e.g. We were chasing (5), but now we can Trap (10) -> Switch immediately
	elif new_priority > (_get_priority(_current_tactic) + 2):
		should_switch = true
		print("[TacticalAssessment] ⚡ PRIORITY JUMP: %s (%d) -> %s (%d)" % [_current_tactic, _get_priority(_current_tactic), new_tactic, new_priority])
	
	if should_switch:
		if new_tactic != _current_tactic:
			print("[TacticalAssessment] 🔄 SWITCH: %s -> %s (Priority: %d)" % [_current_tactic, new_tactic, new_priority])
			_set_tactic(new_tactic, current_time)
	else:
		# Stick to current tactic
		# Update priority in blackboard to match current (even if we didn't switch logic)
		blackboard.set_var("tactical_priority", _get_priority(_current_tactic))
		# print("[TacticalAssessment] 🔒 LOCKED: Keeping %s (Time: %dms)" % [_current_tactic, time_since_switch])
	
	# Store assessment in blackboard
	blackboard.set_var(assessment_var, _current_tactic)
	blackboard.set_var("opponent_escape_routes", opponent_escape_routes)
	blackboard.set_var("opponent_distance", distance)
	
	return SUCCESS if _current_tactic != "NONE" else FAILURE

func _set_tactic(tactic: String, time: int) -> void:
	_current_tactic = tactic
	_tactic_start_time = time
	blackboard.set_var("tactical_priority", _get_priority(tactic))

func _get_priority(tactic: String) -> int:
	match tactic:
		"DEFENSIVE_RETREAT": return 100
		"ONE_TILE_TRAP": return 10
		"CHOKE_POINT": return 9
		"SPACE_DENIAL": return 7
		"AGGRESSIVE_CHASE": return 6
		"WAIT_FOR_DEATH": return 5
		"PREDICTIVE_INTERCEPT": return 4
		_: return 0

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
