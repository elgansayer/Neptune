@tool
extends BTAction
class_name BTWaitAmbush

## Idle/patrol behavior for territorial control
## Bot stays near strategic positions (center, powerups, soft blocks)

@export var patrol_radius: int = 3 ## How far to wander from anchor point
@export var wait_time: float = 1.5 ## Seconds between patrol moves
@export var prefer_center: bool = true ## Gravitate toward map center

var _wait_accumulator: float = 0.0
var _anchor_point: Vector2i = Vector2i.ZERO
var _has_anchor: bool = false

func _generate_name() -> String:
	return "WaitAmbush (radius: %d)" % patrol_radius

func _tick(delta: float) -> int:
	var player = blackboard.get_var("player")
	var grid_sampler = blackboard.get_var("grid_sampler")
	var ai_manager = blackboard.get_var("ai_manager")
	
	if not player or not grid_sampler or not ai_manager:
		return FAILURE
	
	var player_tile = player.get_tile_position()
	
	print("[BTWaitAmbush] _tick called. Tile: ", player_tile)
	
	# Set anchor point if not yet established
	if not _has_anchor:
		if prefer_center:
			# Use map center as anchor
			var map_bounds = grid_sampler.get_map_bounds()
			_anchor_point = Vector2i(map_bounds.x / 2, map_bounds.y / 2)
		else:
			# Use current position as anchor
			_anchor_point = player_tile
		_has_anchor = true
	
	# Wait timer
	_wait_accumulator += delta
	if _wait_accumulator < wait_time:
		# Stand still, no input
		player.set_input(0, 0)
		return RUNNING
	
	# Time to patrol - pick random direction within radius
	_wait_accumulator = 0.0
	
	var distance_from_anchor = grid_sampler.get_manhattan_distance(player_tile, _anchor_point)
	
	# If outside patrol radius, move back toward anchor
	if distance_from_anchor > patrol_radius:
		var direction = (_anchor_point - player_tile)
		var move_dir: Vector2
		
		if abs(direction.x) > abs(direction.y):
			move_dir = Vector2(sign(direction.x), 0)
		else:
			move_dir = Vector2(0, sign(direction.y))
		
		player.set_input(move_dir.x, move_dir.y)
		return RUNNING
	
	# Otherwise, random idle wander
	var random_dir = [Vector2.RIGHT, Vector2.LEFT, Vector2.UP, Vector2.DOWN, Vector2.ZERO].pick_random()
	var target_tile = player_tile + Vector2i(int(random_dir.x), int(random_dir.y))
	
	# Check if walkable
	if grid_sampler.is_tile_walkable(target_tile):
		player.set_input(random_dir.x, random_dir.y)
	else:
		# Stay put if blocked
		player.set_input(0, 0)
	
	return RUNNING # Ambush is continuous behavior
