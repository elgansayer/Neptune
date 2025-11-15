extends Resource
class_name OpponentProfile

## Tracks behavioral patterns of an opponent for adaptive AI tactics
## Based on Bomberman AI Doctrine - Module 5: Advanced Opponent Modelling

# Identity
var player_id: int = 0
var player_name: String = ""

# Observation data
var last_seen_pos: Vector2i = Vector2i.ZERO
var last_seen_time: float = 0.0
var current_path: PackedVector2Array = PackedVector2Array()

# Behavioral scores (updated in real-time via heuristic analysis)
var aggression_score: float = 0.0  # -1.0 (Passive) to +1.0 (Aggressive)
var panic_bomber_rating: float = 0.0  # 0.0 to 1.0 (1.0 = always panic bombs)
var powerup_greed_factor: float = 0.5  # Minimum time_to_spare they'll accept for powerup
var kick_confidence: int = 0  # 0=None, 1=Defensive, 2=Offensive

# Spatial preference (heatmap analysis)
enum Quadrant { Q1, Q2, Q3, Q4, UNKNOWN }
var favourite_quadrant: int = Quadrant.UNKNOWN

# Current tactical state
enum TacticalState { FARMING, HUNTING, EVADING, CONTESTING, UNKNOWN }
var current_state: int = TacticalState.UNKNOWN

# Historical tracking
var _previous_distances: Array[float] = []
var _panic_bomb_events: int = 0
var _total_approaches: int = 0
var _quadrant_time: Dictionary = {}  # Quadrant -> time_spent

func _init(pid: int = 0, pname: String = ""):
	player_id = pid
	player_name = pname

## Update aggression score based on movement towards/away from bot
func update_aggression(dist_now: float, dist_prev: float, delta_multiplier: float = 0.05) -> void:
	if dist_now < dist_prev:
		# Approaching - increase aggression
		aggression_score = lerp(aggression_score, 1.0, delta_multiplier)
	elif dist_now > dist_prev:
		# Fleeing - decrease aggression
		aggression_score = lerp(aggression_score, -1.0, delta_multiplier)
	
	# Clamp to range
	aggression_score = clamp(aggression_score, -1.0, 1.0)

## Record panic bombing event (planted bomb when bot approached within radius)
func record_panic_bomb() -> void:
	_panic_bomb_events += 1
	_total_approaches += 1
	# Fast update on panic
	panic_bomber_rating = lerp(panic_bomber_rating, 1.0, 0.2)

## Record non-panic approach (bot came close, opponent didn't panic)
func record_non_panic_approach() -> void:
	_total_approaches += 1
	# Slow decay on non-panic
	panic_bomber_rating = lerp(panic_bomber_rating, 0.0, 0.02)

## Update powerup greed based on observed risk-taking
func update_greed(time_to_spare: float) -> void:
	# Track minimum time they're willing to accept
	if time_to_spare < powerup_greed_factor:
		powerup_greed_factor = time_to_spare
	
	# Clamp to reasonable range
	powerup_greed_factor = max(0.05, powerup_greed_factor)

## Update quadrant preference
func update_quadrant_time(quadrant: int, delta_time: float) -> void:
	if not _quadrant_time.has(quadrant):
		_quadrant_time[quadrant] = 0.0
	
	_quadrant_time[quadrant] = _quadrant_time[quadrant] + delta_time
	
	# Recalculate favourite
	var max_time := 0.0
	var fav := Quadrant.UNKNOWN
	
	for q in _quadrant_time:
		if _quadrant_time[q] > max_time:
			max_time = _quadrant_time[q]
			fav = q
	
	favourite_quadrant = fav

## Get readable tactical assessment string
func get_tactical_summary() -> String:
	var aggro_text := "Neutral"
	if aggression_score > 0.5:
		aggro_text = "Aggressive"
	elif aggression_score < -0.5:
		aggro_text = "Passive"
	
	var panic_text := "Calm"
	if panic_bomber_rating > 0.7:
		panic_text = "Panic Bomber"
	
	var greed_text := "Cautious"
	if powerup_greed_factor < 0.2:
		greed_text = "Greedy"
	
	return "[%s] %s, %s, %s" % [player_name, aggro_text, panic_text, greed_text]
