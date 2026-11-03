@tool
extends BTAction
class_name BTKickBomb

const SimulationTime = preload("res://shared/ai/simulation_time.gd")
const MovementTiming = preload("res://shared/ai/movement_timing.gd")
const BlastForecast = preload("res://shared/ai/perception/bomb_threat_forecast.gd")

## Kicks a bomb toward an opponent or strategic direction
## Bot walks into a bomb to trigger the kick mechanic
## Requires: has_bomb_kicker = true

@export var kick_target_var: StringName = &"kick_target" ## Target tile to kick toward
@export var max_kick_distance: int = 6 ## Maximum tiles away to attempt kick
@export var confirm_contact := false ## Production actions wait for observed physical contact.
@export var require_tactic := false ## Restrict the attack selector to its selected kick tactic.
@export var require_direct_threat := false ## Aim at an opponent covered by the stopping blast.
@export var attempt_timeout_msec := 800.0
@export var debug_logging := false

var _pending_bomb_id := ""
var _pending_direction := Vector2.ZERO
var _pending_deadline := 0.0

func _enter() -> void:
	_pending_bomb_id = ""
	_pending_direction = Vector2.ZERO

func _exit() -> void:
	if not _pending_bomb_id.is_empty():
		var player = blackboard.get_var("player", null)
		if is_instance_valid(player): player.set_input(0, 0)
	_pending_bomb_id = ""

func _generate_name() -> String:
	return "KickBomb → %s" % kick_target_var

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player")
	var game_instance = blackboard.get_var("game_instance")
	var grid_sampler = blackboard.get_var("grid_sampler")
	
	if not player or not game_instance or not grid_sampler:
		return FAILURE
	
	# Must have bomb kicker ability
	if not player.has_bomb_kicker:
		return FAILURE
	if not _pending_bomb_id.is_empty():
		var pending = game_instance.bombs.get(_pending_bomb_id)
		if is_instance_valid(pending) and pending.bomb_state == ServerBomb.BombState.KICKED and pending.kick_direction.dot(_pending_direction) > 0.9:
			_pending_bomb_id = ""
			blackboard.set_var("kick_contact_confirmed", true)
			return SUCCESS
		if not is_instance_valid(pending) or pending.has_exploded or SimulationTime.milliseconds(blackboard) >= _pending_deadline:
			_pending_bomb_id = ""
			player.set_input(0, 0)
			blackboard.set_var("kick_contact_confirmed", false)
			return FAILURE
		if not _contact_is_safe(player, pending, game_instance):
			_pending_bomb_id = ""
			player.set_input(0, 0)
			return FAILURE
		var retry: Dictionary = player.set_input(_pending_direction.x, _pending_direction.y)
		return RUNNING if retry.accepted else FAILURE
	if require_tactic and blackboard.get_var("tactical_plan", "NONE") != "KICK_SNIPE":
		return FAILURE
	
	var player_tile = player.get_tile_position()
	
	# Get kick target (opponent position or strategic tile)
	var kick_target = blackboard.get_var(kick_target_var, null, false)
	if kick_target == null:
		# Try to get nearest opponent as default target
		var opponent_tracker = blackboard.get_var("opponent_tracker")
		if opponent_tracker:
			var nearest = opponent_tracker.get_nearest_opponent(player.position, player.peer_id)
			if nearest and not nearest.is_empty():
				kick_target = nearest.get("tile", null)
	
	if kick_target == null:
		return FAILURE
	
	# Find kickable bombs in cardinal directions
	var best_bomb = null
	var best_direction = Vector2.ZERO
	var best_score = -1.0
	
	var directions = [
		Vector2i(1, 0),   # Right
		Vector2i(-1, 0),  # Left
		Vector2i(0, 1),   # Down
		Vector2i(0, -1)   # Up
	]
	
	for dir in directions:
		# Check if there's a bomb adjacent to us in this direction
		var bomb_tile = player_tile + dir
		var bomb = _get_bomb_at_tile(bomb_tile, game_instance)
		
		# Check bomb_state instead of is_kicked (BombState.KICKED = 3, PLANTED = 0)
		if bomb == null or bomb.bomb_state != 0:
			continue
		if confirm_contact and not _contact_is_safe(player, bomb, game_instance):
			continue
		
		# Calculate if kicking this bomb would move it toward the target
		var kick_dir = Vector2(dir)
		var score = _score_kick(bomb_tile, kick_dir, kick_target, grid_sampler, game_instance, bomb)
		
		if score > best_score:
			best_score = score
			best_bomb = bomb
			best_direction = kick_dir
	
	if best_bomb == null or best_score < 0.1:
		return FAILURE
	
	# To kick: we need to WALK INTO the bomb
	# Set input direction toward the bomb
	var movement: Dictionary = player.set_input(best_direction.x, best_direction.y)
	if not movement.accepted:
		blackboard.set_var("last_command_rejection", movement.reason)
		return FAILURE
	
	if debug_logging:
		print("[BTKickBomb] Kick intent at %s toward %s (score=%.2f)" % [best_bomb.get_tile_position(), kick_target, best_score])
	
	# Store that we're attempting a kick for follow-up
	blackboard.set_var("last_kick_attempt", SimulationTime.milliseconds(blackboard))
	blackboard.set_var("kick_direction", best_direction)
	if confirm_contact:
		_pending_bomb_id = str(best_bomb.bomb_id)
		_pending_direction = best_direction
		_pending_deadline = SimulationTime.milliseconds(blackboard) + clampf(attempt_timeout_msec, 1.0, 2000.0)
		blackboard.set_var("kick_contact_confirmed", false)
		blackboard.set_var("tactic_executed", "KICK_SNIPE")
		return RUNNING
	
	return SUCCESS

func _get_bomb_at_tile(tile: Vector2i, game_instance) -> Object:
	"""Find a bomb at the given tile position"""
	if not "bombs" in game_instance:
		return null
	
	for bomb_id in game_instance.bombs:
		var bomb = game_instance.bombs[bomb_id]
		if is_instance_valid(bomb) and not bomb.has_exploded:
			if bomb.get_tile_position() == tile:
				return bomb
	return null

func _score_kick(bomb_tile: Vector2i, kick_dir: Vector2, target: Vector2i, grid_sampler, game_instance, bomb) -> float:
	"""Score how good this kick would be
	Returns 0-1 score based on:
	- Does the kick path lead toward the target?
	- Is the path clear for the bomb to travel?
	- Would the bomb's explosion hit the target?
	"""
	var score = 0.0
	
	# Check if kick direction aligns with target
	var to_target = Vector2(target - bomb_tile)
	if to_target.length() < 0.1:
		return 0.0  # Already at target, no point kicking
	
	var alignment = kick_dir.normalized().dot(to_target.normalized())
	if alignment < 0.5:
		return 0.0  # Kicking away from target
	
	score += alignment * 0.5  # Up to 0.5 for alignment
	
	# Check how far the bomb would travel in this direction
	var travel_distance = 0
	var current_tile = bomb_tile
	var bomb_range: int = bomb.explosion_range
	
	for i in range(1, clampi(max_kick_distance, 1, 32) + 1):
		var check_tile = bomb_tile + Vector2i(kick_dir * float(i))
		var tile_type = game_instance.get_tile_type(check_tile) if game_instance.has_method("get_tile_type") else -1
		
		if tile_type != 0:  # Not empty floor
			break
		if confirm_contact and float(game_instance.active_explosion_tiles.get("%d,%d" % [check_tile.x, check_tile.y], -INF)) >= SimulationTime.milliseconds(blackboard):
			return 0.0
		
		# Check for obstacles (other bombs, players would stop it)
		if grid_sampler.is_tile_occupied(check_tile):
			break
		
		travel_distance = i
		current_tile = check_tile
	
	if travel_distance == 0:
		return 0.0  # Bomb can't move
	var blast: Array[Vector2i] = BlastForecast.project(current_tile, bomb_range, grid_sampler)
	if confirm_contact:
		var player = blackboard.get_var("player")
		if blast.has(player.get_tile_position()): return 0.0
	if require_direct_threat and not blast.has(target):
		return 0.0
	
	# Check if final position would put target in blast range
	var final_dist_to_target = abs(current_tile.x - target.x) + abs(current_tile.y - target.y)
	if final_dist_to_target <= bomb_range:
		score += 0.5  # Target would be in blast!
	elif final_dist_to_target <= bomb_range + 2:
		score += 0.25  # Close to target
	
	return score

func _contact_is_safe(player, bomb, game_instance) -> bool:
	var now := SimulationTime.milliseconds(blackboard)
	var observation: Dictionary = bomb.get_forecast_observation()
	# Remote and non-normal movement require their own trajectory contract.
	if int(observation.get("bomb_type", 0)) != ServerBomb.BOMB_TYPE_NORMAL:
		return false
	var speed := MovementTiming.tiles_per_second(player)
	if speed <= 0.0: return false
	var contact_msec := 1000.0 / speed + 2.0 * 1000.0 / Engine.physics_ticks_per_second + 100.0
	if (float(observation.fuse_lower_bound) - float(observation.elapsed)) * 1000.0 <= contact_msec:
		return false
	var manager = blackboard.get_var("ai_manager", null)
	var threats: Dictionary = manager.get_current_threat_matrix() if manager else {}
	for cell in [player.get_tile_position(), bomb.get_tile_position()]:
		var key := "%d,%d" % [cell.x, cell.y]
		if float(game_instance.active_explosion_tiles.get(key, -INF)) >= now:
			return false
		# An observed earlier bomb can shorten this bomb's fuse through a
		# chain. Its nominal bound cannot authorize contact after that deadline.
		if float(threats.get(key, INF)) <= now + contact_msec:
			return false
	return true
