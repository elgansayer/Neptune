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
	
	# CRITICAL PRE-FLIGHT SAFETY CHECK: Verify escape route one final time
	# This prevents suicide if situation changed since planning
	var bomb_safety_checker = blackboard.get_var("bomb_safety_checker")
	if bomb_safety_checker:
		var current_time_msec = Time.get_ticks_msec()
		var bomb_range = player.bomb_range if player else 2
		var bot_speed = 5.0 # tiles per second
		
		var is_safe = bomb_safety_checker.can_safely_plant_bomb(
			player_tile, # bot position
			player_tile, # bomb position (same as bot)
			bomb_range,
			bot_speed,
			current_time_msec
		)
		
		if not is_safe:
			print("[BTPlaceBomb] ⚠ PRE-FLIGHT ABORT: Safety check failed at placement time!")
			return FAILURE
	
	# Place the bomb
	game_instance.place_bomb(player)
	
	print("[BTPlaceBomb] ✓ Placed bomb at ", player_tile)
	
	# Store bomb placement info in blackboard for debugging/tracking
	blackboard.set_var("last_bomb_placed_at", player_tile)
	blackboard.set_var("last_bomb_placed_time", Time.get_ticks_msec() / 1000.0)
	
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
