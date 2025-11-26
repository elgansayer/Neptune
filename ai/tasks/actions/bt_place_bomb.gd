@tool
extends BTAction
class_name BTPlaceBomb

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
	
	
	# CONTEXT-AWARE SAFETY: Be STRICT if enemies nearby, RELAXED if farming alone
	# Check for nearby opponents
	var has_nearby_enemies = false
	var opponent_tracker = blackboard.get_var("opponent_tracker", null)
	if opponent_tracker and opponent_tracker.has_method("get_closest_opponent"):
		var closest = opponent_tracker.get_closest_opponent(player_tile)
		if closest and closest.has("distance"):
			# Enemy within 8 tiles = combat situation, be STRICT
			has_nearby_enemies = closest["distance"] <= 8.0
	
	# CRITICAL PRE-FLIGHT SAFETY CHECK: Verify escape route one final time
	# This prevents suicide if situation changed since planning
	var bomb_safety_checker = blackboard.get_var("bomb_safety_checker")
	if bomb_safety_checker:
		var current_time_msec = Time.get_ticks_msec()
		var bomb_range = player.bomb_range if player else 2
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
				current_time_msec
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
				current_time_msec
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
			
			if not is_safe:
				# No safe tile with further exits found, but check margin
				# If margin is VERY high (>1500ms), the escape tile is technically safe
				# even if it's a "dead end" - bot can wait there until bomb clears
				# This allows farming in corner areas surrounded by soft blocks
				if margin_ms >= 1500.0:
					print("[BTPlaceBomb] ⚠ MARGINAL SAFE: escape=%s margin=%.0fms (dead end but survivable)" % [escape_tile, margin_ms])
					# Continue to place bomb - it's survivable even if not ideal
				else:
					print("[BTPlaceBomb] ⚠ PRE-FLIGHT ABORT: No escape tile outside blast zone. Margin was: %.0fms (need 1500+)" % margin_ms)
					return FAILURE
	
	# Place the bomb
	game_instance.place_bomb(player)
	
	print("[BTPlaceBomb] ✓ Placed bomb at ", player_tile)
	
	# CRITICAL: Store bomb placement info and trigger IMMEDIATE escape mode
	blackboard.set_var("last_bomb_placed_at", player_tile)
	blackboard.set_var("last_bomb_placed_time", Time.get_ticks_msec() / 1000.0)
	
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

func _coerce_to_tile(value) -> Vector2i:
	"""Convert various types to Vector2i tile position"""
	if value is Vector2i:
		return value
	if value is Vector2:
		return Vector2i(int(value.x), int(value.y))
	return Vector2i(-1, -1)
