extends AStarGrid2D
class_name DangerAwareAStar

## Time-aware pathfinding that avoids bomb threats
## Overrides cost calculation to make lethal tiles impassable
## Based on Bomberman AI Doctrine - Godot-Specific Implementation

# Reference to global threat data (Vector2i -> lethal_time_msec)
var threat_matrix_ref: Dictionary = {}

# Path start time in milliseconds
var path_start_time_msec: float = 0.0

# Starting position for path calculation
var path_start_pos: Vector2i = Vector2i.ZERO

# Bot movement speed (milliseconds per tile)
var bot_speed_msec_per_tile: float = 200.0  # Default: (1.0 / 5.0) * 1000.0

# Safety buffer to avoid cutting it too close
var safety_buffer_msec: float = 100.0  # 0.1s buffer

## Override: Calculate cost to move from one tile to another
func _compute_cost(from_id: Vector2i, to_id: Vector2i) -> float:
	# 1. Base cost (always 1 for grid movement)
	var cost := 1.0
	
	# 2. Get threat data for destination tile
	if not threat_matrix_ref.has(to_id):
		# Tile is perfectly safe - no threat
		return cost
	
	var tile_lethal_time_msec: float = threat_matrix_ref[to_id]
	
	# 3. Calculate distance traveled to reach 'from_id'
	# Use Manhattan distance from start position (not actual path cost to avoid recursion)
	var dist_to_from_id: int = abs(from_id.x - path_start_pos.x) + abs(from_id.y - path_start_pos.y)
	var time_at_from_id: float = path_start_time_msec + (dist_to_from_id * bot_speed_msec_per_tile)
	
	# 4. Calculate arrival time at destination
	var arrival_time_at_to_id: float = time_at_from_id + bot_speed_msec_per_tile
	
	# 5. CRITICAL CHECK: Will we arrive before tile explodes?
	if arrival_time_at_to_id >= (tile_lethal_time_msec - safety_buffer_msec):
		# LETHAL PATH - we arrive at/after explosion
		# Return infinity to make A* treat this as impossible
		return INF
	
	# 6. PENALTY BOX: Tile will explode but we'll be gone
	# Prefer paths that stay further from danger
	var time_to_spare: float = tile_lethal_time_msec - arrival_time_at_to_id
	
	# Exponential penalty as we get closer to explosion time
	# Less time to spare = higher penalty
	var penalty := 1000.0 / pow(time_to_spare, 2.0)
	
	return cost + penalty

## Override: Estimate remaining distance (heuristic)
func _estimate_cost(from_id: Vector2i, to_id: Vector2i) -> float:
	# Manhattan distance (4-directional movement)
	return abs(to_id.x - from_id.x) + abs(to_id.y - from_id.y)
