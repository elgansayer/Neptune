@tool
extends BTAction
class_name BTPlaceBomb

const SimulationTime = preload("res://shared/ai/simulation_time.gd")

## Places a bomb at the player's current position
## Checks if player can place a bomb before attempting

@export var check_capacity: bool = true ## Verify player hasn't exceeded max bombs
@export var check_existing: bool = true ## Verify no bomb already at position
@export var require_at_target: bool = true ## Only plant if at target_cell (for farming)
@export var target_cell_var: StringName = &"target_cell" ## Target to verify against

func _generate_name() -> String:
	return "PlaceBomb"

func _tick(delta: float) -> int:
	var player = blackboard.get_var("player")
	var game_instance = blackboard.get_var("game_instance")
	
	# Early exit if player is dead
	if player and player.is_dead:
		return FAILURE
	
	# print("[BTPlaceBomb] Tick") # Uncomment for verbose debugging
	
	if not player:
		push_warning("[BTPlaceBomb] Missing player in blackboard")
		return FAILURE
	
	if not game_instance:
		push_warning("[BTPlaceBomb] Missing game_instance in blackboard")
		return FAILURE
	
	var player_tile = player.get_tile_position()
	
	# If require_at_target is enabled, verify we're at the target cell before planting
	if require_at_target:
		var target_val = blackboard.get_var(target_cell_var)
		if target_val == null:
			# No target set, cannot verify position
			print("[BTPlaceBomb] REJECTED: Target var '", target_cell_var, "' is null")
			return FAILURE
			
		var target_tile = _coerce_to_tile(target_val)
		if target_tile != Vector2i(-1, -1) and player_tile != target_tile:
			# Not at target yet, move failed or incomplete
			print("[BTPlaceBomb] REJECTED: Not at target tile yet. Current=", player_tile, " Target=", target_tile)
			return FAILURE
	
	# Check if player can place a bomb
	if check_capacity and not player.can_place_bomb():
		# Can't place bomb (at max capacity or cooldown)
		print("[BTPlaceBomb] REJECTED: Cannot place bomb (capacity/cooldown). Bombs=", player.bombs_placed, "/", player.max_bombs)
		return FAILURE
	
	# Check if there's already a bomb at this position
	if check_existing:
		if _bomb_at_position(player_tile, game_instance):
			# Already a bomb here
			return FAILURE
	
	# CRITICAL: Validate bomb has PURPOSE (soft blocks to destroy OR opponent in range OR tactical attack)
	# This prevents useless bombs in open areas UNLESS we're executing an attack tactic
	var grid_sampler = blackboard.get_var("grid_sampler")
	var bomb_range = player.get_effective_bomb_range() if player else 2
	var has_purpose = false
	
	# Check if we're executing a tactical attack - if so, bomb has purpose!
	var current_tactic = blackboard.get_var("tactical_plan", "NONE")
	var attack_tactics = ["CORNER_TRAP", "BODY_BLOCK", "ONE_TILE_TRAP", "DOUBLE_BOMB", 
						  "CHOKE_POINT", "TUNNEL_PRESSURE", "SPACE_DENIAL", "STUTTER_TRAP",
						  "ITEM_HUNTER_TRAP", "AGGRESSIVE_CHASE", "PREDICTIVE_INTERCEPT"]
	if current_tactic in attack_tactics:
		has_purpose = true  # Tactical attack bombs always have purpose!
	
	# Check for soft blocks in blast range (farming bombs)
	if not has_purpose:
		var soft_blocks = _count_soft_blocks_in_range(player_tile, bomb_range, grid_sampler, game_instance)
		if soft_blocks > 0:
			has_purpose = true
	
	# Check for opponents in blast range (this is a tactical bomb)
	if not has_purpose:
		var opponent_tracker = blackboard.get_var("opponent_tracker")
		if opponent_tracker:
			var nearest = opponent_tracker.get_nearest_opponent(player.position, player.peer_id)
			if nearest and not nearest.is_empty():
				var opp_tile = nearest.get("tile", Vector2i(-99, -99))
				var distance = abs(opp_tile.x - player_tile.x) + abs(opp_tile.y - player_tile.y)
				# Opponent is close enough that this bomb is tactical (increased range for aggression)
				if distance <= bomb_range + 5:
					has_purpose = true
	
	if not has_purpose:
		print("[BTPlaceBomb] REJECTED: No purpose (no soft blocks or opponents in range, tactic=%s)" % current_tactic)
		return FAILURE
	
	
	# CONTEXT-AWARE SAFETY: Be STRICT if enemies nearby OR attacking, RELAXED if farming alone
	# Check for nearby opponents (reuse opponent_tracker from above if set)
	var has_nearby_enemies = false
	
	# CRITICAL: If executing attack tactic, ALWAYS use strict safety!
	if current_tactic in attack_tactics:
		has_nearby_enemies = true  # Force strict mode for attack tactics
	else:
		var opp_tracker = blackboard.get_var("opponent_tracker", null)
		if opp_tracker and opp_tracker.has_method("get_closest_opponent"):
			var closest = opp_tracker.get_closest_opponent(player_tile)
			if closest and closest.has("distance"):
				# Enemy within 8 tiles = combat situation, be STRICT
				has_nearby_enemies = closest["distance"] <= 8.0
	
	# CRITICAL: DEAD-END POSITION CHECK
	# If bot is already in a dead end (only 1 walkable neighbor), do NOT place more bombs!
	# This prevents suicide when bot escapes to dead end then tries to chain-bomb
	var exit_count = _count_walkable_exits(player_tile, grid_sampler, game_instance)
	if exit_count <= 1:
		# Dead end or corner - if we already have a bomb active, don't place another
		var active_bomb_count = _count_active_player_bombs(player, game_instance)
		if active_bomb_count > 0:
			print("[BTPlaceBomb] ⚠ DEAD-END ABORT: Already in dead end (exits=%d) with %d active bombs!" % [exit_count, active_bomb_count])
			return FAILURE
		# Allow first bomb to break out of dead end
		print("[BTPlaceBomb] ⚠ Dead end (exits=%d), but allowing first bomb to break out" % exit_count)
	
	# CRITICAL PRE-FLIGHT SAFETY CHECK: Verify escape route one final time
	# This prevents suicide if situation changed since planning
	var bomb_safety_checker = blackboard.get_var("bomb_safety_checker")
	if bomb_safety_checker:
		var current_time_msec = SimulationTime.milliseconds(blackboard)
		# bomb_range already declared above
		var bot_speed = 5.0 # tiles per second
		
		# STRICT MODE (enemies nearby): MUST have safe escape
		# RELAXED MODE (farming alone): Allow if there's ANY path, even risky
		if has_nearby_enemies:
			# STRICT: Use standard safety check
			var is_safe = bomb_safety_checker.can_safely_plant_bomb(
				player_tile,
				player_tile,
				bomb_range,
				bot_speed,
				current_time_msec,
				player.get_bomb_fuse_lower_bound()
			)
			
			if not is_safe:
				print("[BTPlaceBomb] ⚠ PRE-FLIGHT ABORT: Enemies nearby, no safe escape!")
				return FAILURE
		else:
			# RELAXED: Check if there's ANY reachable tile (even if tight)
			# Use detailed check to see best option
			var safety_result = bomb_safety_checker.check_plant_safety_detailed(
				player_tile,
				player_tile,
				bomb_range,
				bot_speed,
				current_time_msec,
				false, player.get_bomb_fuse_lower_bound()
			)
			
			# If we explored 0 tiles, we're completely blocked (shouldn't happen)
			# If we explored >0 tiles, there's SOME path (trust the farming escape logic)
			if safety_result.get("explored_tiles", 0) == 0:
				print("[BTPlaceBomb] ⚠ PRE-FLIGHT ABORT: Completely blocked, cannot move!")
				return FAILURE
			
			# Check if there's a safe escape route
			var is_safe = safety_result.get("safe", false)
			var margin_ms = safety_result.get("margin_ms", 0)
			var escape_tile = safety_result.get("escape_tile", Vector2i(-1, -1))
			
			# CRITICAL: If escape_tile is invalid (-1, -1), there is NO escape at all!
			# This is a DEATH TRAP - do not place bomb!
			if escape_tile == Vector2i(-1, -1):
				print("[BTPlaceBomb] ⚠ PRE-FLIGHT ABORT: NO ESCAPE TILE FOUND - DEATH TRAP!")
				return FAILURE
			
			if not is_safe:
				# No safe tile with further exits found
				# COMPETITIVE bots are more aggressive - lower margin requirement
				var personality = blackboard.get_var("personality", "BALANCED")
				var required_margin = 3000.0  # Default conservative
				if personality == "COMPETITIVE":
					required_margin = 1500.0  # Competitive bots take risks
				elif personality == "AGGRESSIVE":
					required_margin = 2000.0
				
				if margin_ms >= required_margin:
					print("[BTPlaceBomb] ⚠ MARGINAL SAFE: escape=%s margin=%.0fms (personality=%s allows %.0fms)" % [escape_tile, margin_ms, personality, required_margin])
					# Continue to place bomb - margin is acceptable for this personality
				else:
					print("[BTPlaceBomb] ⚠ PRE-FLIGHT ABORT: Dead end margin %.0fms < required %.0fms" % [margin_ms, required_margin])
					return FAILURE
	
	# Place the bomb
	var placement: Dictionary = game_instance.place_bomb(player)
	if not placement.accepted:
		blackboard.set_var("last_bomb_rejection", placement.reason)
		return FAILURE
	blackboard.set_var("last_bomb_rejection", "")
	
	print("[BTPlaceBomb] ✓ Placed bomb at ", player_tile)
	
	# CRITICAL: Store bomb placement info and trigger IMMEDIATE escape mode
	blackboard.set_var("last_bomb_placed_at", player_tile)
	blackboard.set_var("last_bomb_placed_time", SimulationTime.seconds(blackboard))
	
	# SAFETY: Force bot into danger mode so it escapes immediately
	blackboard.set_var("in_danger", true)
	blackboard.set_var("danger_tile", player_tile)
	
	# CRITICAL: Clear any farming target to prevent re-planting at same spot
	blackboard.set_var("target_cell", null)
	
	return SUCCESS

func _bomb_at_position(tile: Vector2i, game_instance) -> bool:
	"""Check if there's already a bomb at the given tile"""
	for bomb_id in game_instance.bombs:
		var bomb = game_instance.bombs[bomb_id]
		if is_instance_valid(bomb) and bomb.get_tile_position() == tile:
			return true
	return false

func _count_soft_blocks_in_range(center: Vector2i, bomb_range: int, grid_sampler, game_instance) -> int:
	"""Count soft blocks that would be destroyed by a bomb at this position"""
	if not grid_sampler:
		return 0
	
	var count = 0
	var directions = [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]
	
	for dir in directions:
		for dist in range(1, bomb_range + 1):
			var check_tile = center + (dir * dist)
			var tile_type = game_instance.get_tile_type(check_tile) if game_instance.has_method("get_tile_type") else grid_sampler.get_tile_type(check_tile)
			if tile_type == 1:  # Hard block - stops blast
				break
			elif tile_type == 2:  # Soft block - counts and stops blast
				count += 1
				break
	return count

func _coerce_to_tile(value) -> Vector2i:
	"""Convert various types to Vector2i tile position"""
	if value is Vector2i:
		return value
	if value is Vector2:
		return Vector2i(int(value.x), int(value.y))
	return Vector2i(-1, -1)

func _count_walkable_exits(tile: Vector2i, grid_sampler, game_instance) -> int:
	"""Count the number of walkable exits from a position (ignoring bombs for static geometry check)"""
	var count = 0
	var directions = [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]
	
	for dir in directions:
		var neighbor = tile + dir
		# Check if neighbor is walkable (floor tile, not wall or soft block)
		var tile_type = -1
		if game_instance and game_instance.has_method("get_tile_type"):
			tile_type = game_instance.get_tile_type(neighbor)
		elif grid_sampler and grid_sampler.has_method("get_tile_type"):
			tile_type = grid_sampler.get_tile_type(neighbor)
		
		if tile_type == 0:  # Floor tile = walkable exit
			count += 1
	
	return count

func _count_active_player_bombs(player, game_instance) -> int:
	"""Count how many active (unexploded) bombs this player has placed"""
	if not game_instance or not "bombs" in game_instance:
		return 0
	
	var count = 0
	var player_id_str = str(player.peer_id)  # Convert peer_id to string for comparison
	for bomb_id in game_instance.bombs:
		var bomb = game_instance.bombs[bomb_id]
		if is_instance_valid(bomb) and not bomb.has_exploded:
			# Compare owner_id (string) to player's peer_id as string
			if bomb.owner_id == player_id_str:
				count += 1
	return count
