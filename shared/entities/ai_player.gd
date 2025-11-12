extends "res://shared/entities/server_player.gd"
# AIPlayer - AI-Controlled Player
# Note: Using full resource path instead of class_name to fix parse issues
# Extends ServerPlayer but generates input locally instead of from network

const AIBotController = preload("res://shared/ai/ai_bot_controller.gd")
const ImprovedAIController = preload("res://shared/ai/improved_ai_controller.gd")
const AIPersonality = preload("res://shared/ai/ai_personalities.gd")

var controller  # Can be AIBotController or ImprovedAIController
var personality_type: int  # AIPersonality.Type enum value
var bot_name: String = "Bot"
var use_improved_ai: bool = true  # Set to true to use new intelligent AI

# Spawn delay
var spawn_time: float = 0.0
var is_active: bool = false
const SPAWN_DELAY: float = 3.0

# Tile-snapped movement for AI
var tile_movement_enabled: bool = true  # AI moves tile-to-tile
var current_target_tile: Vector2i = Vector2i(-1, -1)
var current_logic_tile: Vector2i = Vector2i(-1, -1)  # The tile we're "on" for game logic
var tile_movement_progress: float = 0.0
var tile_movement_speed: float = 2.8125  # Tiles per second (2.8125 * 64 = 180 pixels/sec)

func get_tile_position() -> Vector2i:
	"""Override to return logic tile during tile movement"""
	if tile_movement_enabled and current_logic_tile != Vector2i(-1, -1):
		return current_logic_tile
	else:
		return super.get_tile_position()

func is_ai_bot() -> bool:
	"""Helper to identify AI players"""
	return true

func setup_ai(game_instance: Node2D, personality: int = 0):  # 0 = BALANCED
	"""Initialize AI controller with personality"""
	personality_type = personality
	
	# Set spawn time for delay
	spawn_time = Time.get_ticks_msec() / 1000.0
	
	# Choose AI controller type
	if use_improved_ai:
		controller = ImprovedAIController.new(game_instance, personality)
		print("[AIPlayer] Using IMPROVED AI system")
	else:
		controller = AIBotController.new(game_instance, personality)
		print("[AIPlayer] Using legacy AI system")
	
	# Generate bot name based on personality
	var personality_name = controller.get_personality_name()
	var bot_number = randi() % 1000
	bot_name = "%s_Bot_%03d" % [personality_name, bot_number]
	username = bot_name
	
	print("[AIPlayer] Initialized: ", bot_name, " (", personality_name, ") at time ", spawn_time)
	
	# Setup debug visualizer if in debug mode (deferred until in scene tree)
	if OS.is_debug_build() and use_improved_ai:
		# Defer setup until we're in the scene tree
		call_deferred("_setup_debug_visualizer_deferred", game_instance)

func _setup_debug_visualizer_deferred(game_ref: Node2D):
	"""Deferred debug visualizer setup after AI is in scene tree"""
	if is_instance_valid(controller) and controller.has_method("setup_debug_visualizer"):
		controller.setup_debug_visualizer(game_ref, self)

func _physics_process(delta):
	"""Override physics process for AI-specific behavior"""
	# Enforce spawn delay
	if not is_active:
		var time_since_spawn = (Time.get_ticks_msec() / 1000.0) - spawn_time
		if time_since_spawn >= SPAWN_DELAY:
			is_active = true
			print("[AIPlayer] ", bot_name, " is now active after ", time_since_spawn, "s")
		else:
			# Still in delay, do nothing
			return
			
	if not controller:
		print("[AIPlayer] ERROR: No controller for ", bot_name)
		super._physics_process(delta)
		return
	
	if is_dead:
		# Ensure dead bots stay inactive
		super._physics_process(delta)
		return
	
	# Generate AI decision
	var input_data: Dictionary = controller.decide_action(self)
	
	if tile_movement_enabled:
		# TILE-SNAPPED MOVEMENT for cleaner pathfinding
		_physics_process_tile_movement(delta, input_data)
	else:
		# Standard continuous movement (original behavior)
		_physics_process_continuous(delta, input_data)

func _physics_process_continuous(delta: float, input_data: Dictionary):
	"""Original continuous movement system"""
	# DIAGNOSTIC LOGGING - Trace decision → movement pipeline
	var frame = Engine.get_physics_frames()
	if frame % 30 == 0:  # Log every 0.5 seconds
		var reasoning = input_data.get("reasoning", "UNKNOWN")
		var tile_pos = get_tile_position()
		var debug_dir: Vector2 = input_data.get("direction", Vector2.ZERO)
		
		print("[AIPlayer] %s Frame:%d Tile:%s Decision:%s Dir:%s (%.2f,%.2f) PlaceBomb:%s" % [
			bot_name, frame, tile_pos, reasoning, 
			"ZERO" if debug_dir.length() < 0.01 else "MOVING",
			debug_dir.x, debug_dir.y,
			input_data.get("place_bomb", false)
		])
	
	# Apply AI-generated input (use bracket access for Dictionary)
	var dir: Vector2 = input_data.get("direction", Vector2.ZERO)
	set_input(dir.x, dir.y)
	
	# Check if we got stuck (set by ServerPlayer)
	if has_meta("stuck_frame") and get_meta("stuck_frame") == Engine.get_physics_frames():
		# Force immediate replan on next decision
		if "force_replan" in controller:
			controller.force_replan = true
		remove_meta("stuck_frame")
		if Engine.get_physics_frames() % 30 == 0:
			print("[AIPlayer] ", bot_name, " detected STUCK, forcing replan")
	
	# Check if recovery mode was triggered (forced replan)
	if has_meta("force_replan"):
		if "force_replan" in controller:
			controller.force_replan = true
			print("[AIPlayer] ", bot_name, " entering recovery - AI will replan")
		remove_meta("force_replan")
	
	# Store bomb request for game_instance to process
	if input_data.get("place_bomb", false) and can_place_bomb():
		request_bomb_placement()
	
	# Call parent physics process to handle movement
	super._physics_process(delta)

func _physics_process_tile_movement(delta: float, input_data: Dictionary):
	"""Tile-snapped movement system - cleaner for AI pathfinding"""
	var desired_dir = input_data.get("direction", Vector2.ZERO)
	var want_bomb = input_data.get("place_bomb", false)
	
	# Get current tile position using parent's method (pixel-based)
	var pixel_tile = super.get_tile_position()
	
	# Initialize logic tile if not set
	if current_logic_tile == Vector2i(-1, -1):
		current_logic_tile = pixel_tile
		var tile_center = Vector2(current_logic_tile) * Constants.TILE_SIZE + Vector2.ONE * (Constants.TILE_SIZE / 2.0)
		position = tile_center
	
	# If no target or reached target, snap and check for new direction
	if current_target_tile == Vector2i(-1, -1) or tile_movement_progress >= 1.0:
		# Snap to exact tile center
		var tile_center = Vector2(current_logic_tile) * Constants.TILE_SIZE + Vector2.ONE * (Constants.TILE_SIZE / 2.0)
		position = tile_center
		velocity = Vector2.ZERO
		tile_movement_progress = 0.0
		current_target_tile = Vector2i(-1, -1)
		
		# Handle bomb request when stationary on tile
		if want_bomb and can_place_bomb():
			request_bomb_placement()
		
		# Check if AI wants to move
		if desired_dir.length() > 0.01:
			# Calculate next tile based on 4-way direction
			var next_tile = current_logic_tile
			if abs(desired_dir.x) > abs(desired_dir.y):
				next_tile.x += int(sign(desired_dir.x))
			else:
				next_tile.y += int(sign(desired_dir.y))
			
			# Check if next tile is walkable
			var game_instance = get_parent()
			if game_instance and game_instance.has_method("is_tile_walkable"):
				if game_instance.is_tile_walkable(next_tile):
					current_target_tile = next_tile
					last_move_direction = (Vector2(next_tile) - Vector2(current_logic_tile)).normalized()
					
					if Engine.get_physics_frames() % 30 == 0:
						var reasoning = input_data.get("reasoning", "UNKNOWN")
						print("[AIPlayer-Tile] %s %s->%s Decision:%s" % [bot_name, current_logic_tile, next_tile, reasoning])
				else:
					# Blocked! Signal AI to replan
					if "force_replan" in controller:
						controller.force_replan = true
					if Engine.get_physics_frames() % 60 == 0:
						print("[AIPlayer-Tile] %s BLOCKED at %s, wanted %s" % [bot_name, current_logic_tile, next_tile])
		
		move_and_slide()
		return
	
	# Currently moving to target tile - smooth interpolation
	var start_pos = Vector2(current_logic_tile) * Constants.TILE_SIZE + Vector2.ONE * (Constants.TILE_SIZE / 2.0)
	var end_pos = Vector2(current_target_tile) * Constants.TILE_SIZE + Vector2.ONE * (Constants.TILE_SIZE / 2.0)
	
	var distance = start_pos.distance_to(end_pos)
	var movement_time = distance / (tile_movement_speed * Constants.TILE_SIZE)
	tile_movement_progress += delta / movement_time
	
	# When we cross the halfway point, update logic tile
	if tile_movement_progress >= 0.5 and current_logic_tile != current_target_tile:
		current_logic_tile = current_target_tile
		if Engine.get_physics_frames() % 60 == 0:
			print("[AIPlayer-Tile] %s crossed halfway, logic tile now %s" % [bot_name, current_logic_tile])
	
	tile_movement_progress = min(tile_movement_progress, 1.0)
	
	# Smooth movement with easing
	var eased_progress = ease(tile_movement_progress, 0.5)  # Slight ease for smoothness
	position = start_pos.lerp(end_pos, eased_progress)
	velocity = (end_pos - start_pos).normalized() * tile_movement_speed * Constants.TILE_SIZE
	
	move_and_slide()

func get_bot_info() -> Dictionary:
	"""Returns information about this bot for debugging"""
	return {
		"name": bot_name,
		"personality": controller.get_personality_name() if controller else "None",
		"position": position,
		"tile": get_tile_position(),
		"bombs_available": max_bombs - bombs_placed,
		"bomb_range": bomb_range
	}
