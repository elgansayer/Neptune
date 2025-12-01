extends Node

## GameConfig - Runtime game configuration loaded from map metadata
## This replaces hardcoded constants with values from the active map
##
## SATURN BOMBERMAN MOVEMENT SYSTEM
## ================================
## Uses sub-pixel accumulator for deterministic, integer-based movement.
## At 16px reference tile size:
## - Base movement: 1 pixel per frame (60 px/sec)
## - Each roller skate adds 32 to accumulator per frame
## - Accumulator overflows at 256, granting +1 pixel that frame
## - Max speed (8 skates): 2 pixels per frame (120 px/sec)
##
## Speed Tier Table (at 16px tile size):
## | Skates | Accumulator Add | Avg Speed (px/frame) |
## |--------|-----------------|----------------------|
## | 0      | 0               | 1.000                |
## | 1      | 32              | 1.125                |
## | 2      | 64              | 1.250                |
## | 3      | 96              | 1.375                |
## | 4      | 128             | 1.500                |
## | 5      | 160             | 1.625                |
## | 6      | 192             | 1.750                |
## | 7      | 224             | 1.875                |
## | 8      | 256             | 2.000                |

# === MAP-DEPENDENT VALUES (loaded from map metadata) ===
var TILE_SIZE: int = 64 # Default, overridden by map metadata
var map_width: int = 17
var map_height: int = 11
var map_name: String = "Unknown"
var spawn_points: Array = []

# === DYNAMIC SCALING (computed from TILE_SIZE) ===
# Reference tile size: 16px (Saturn Bomberman native)
const REFERENCE_TILE_SIZE = 16.0
var scale_factor: float = 4.0 # TILE_SIZE / REFERENCE_TILE_SIZE (default 64/16)

# === SATURN BOMBERMAN SPEED SYSTEM ===
# These are the core constants from Saturn Bomberman's accumulator model
const SATURN_BASE_PIXELS_PER_FRAME: int = 1 # Base movement: 1 pixel/frame at 16px tiles
const SATURN_ACCUMULATOR_MAX: int = 256 # Overflow threshold
const SATURN_SKATE_INCREMENT: int = 32 # Each skate adds 32 to accumulator per frame
const SATURN_MAX_SKATES: int = 8 # Maximum roller skates (caps at 2 px/frame)
const SATURN_MAX_PIXELS_PER_FRAME: int = 2 # Hard cap to prevent collision tunneling

# Scaled base speed (pixels per second at current tile size)
# At 16px tiles: 1 pixel/frame * 60 fps = 60 px/sec
# At 64px tiles: 4 pixels/frame * 60 fps = 240 px/sec
var BASE_SPEED: float = 240.0 # Computed in load_map_config()

# Reference values for other mechanics (at 16px tile size)
const SNAP_TO_CENTER_SPEED_REFERENCE = 30.0 # Snap speed at 16px tile size
const CORNER_ASSIST_THRESHOLD_REFERENCE = 5.0 # Corner assist at 16px tile size (Saturn: ~5px tolerance)
const COLLISION_CHECK_DISTANCE_REFERENCE = 2.0 # Collision check distance at 16px tile size

# PLAYER_HALF_WIDTH: Player hitbox is 12x12 at 16px tiles (75% of tile)
# This provides 2px buffer on each side for easier corridor navigation
var PLAYER_HALF_WIDTH: float = 24.0 # Default for 64px tiles (75% of 64 / 2 = 24)

# Scaled values (computed in load_map_config)
var SNAP_TO_CENTER_SPEED: float = 120.0 # SNAP_TO_CENTER_SPEED_REFERENCE * scale_factor
var CORNER_ASSIST_THRESHOLD: float = 20.0 # CORNER_ASSIST_THRESHOLD_REFERENCE * scale_factor
var COLLISION_CHECK_DISTANCE: float = 8.0 # COLLISION_CHECK_DISTANCE_REFERENCE * scale_factor
var SNAP_THRESHOLD: float = 2.0 # Scaled proportionally

# Collision Layers (physics layer bit positions)
const COLLISION_LAYER_WALLS = 1 # Layer 1 (bit 0): Solid/destructible walls
const COLLISION_LAYER_PLAYERS = 2 # Layer 2 (bit 1): Player characters
const COLLISION_LAYER_BOMBS = 4 # Layer 3 (bit 2): Bombs
const COLLISION_LAYER_EXPLOSIONS = 8 # Layer 4 (bit 3): Explosion damage areas
const COLLISION_LAYER_POWERUPS = 16 # Layer 5 (bit 4): Power-up items

# Movement (multipliers are dimensionless, don't scale)
const WALK_MULTIPLIER = 0.6
const RUN_MULTIPLIER = 1.0
const WALK_RUN_THRESHOLD = 0.5
const INPUT_DEADZONE = 0.1
const CORNER_ASSIST_SPEED_MULTIPLIER = 0.8

# Bomb
const BOMB_TIMER = 3.0
const EXPLOSION_DURATION = 1.0
const DEFAULT_BOMB_RANGE = 2

# Network
const SERVER_PORT = 7777
const MAX_PLAYERS = 8
const TICK_RATE = 60 # Server physics runs at 60 FPS
const NETWORK_SEND_RATE = 20 # Send state updates 20 times per second

# Player states
enum PlayerState {
	IDLE,
	MOVING,
	DEAD,
	STUNNED
}

# Directions
enum Direction {
	UP,
	DOWN,
	LEFT,
	RIGHT
}

func load_map_config(map_data: Dictionary):
	"""Load configuration from map metadata"""
	if map_data.has("tile_size"):
		TILE_SIZE = map_data.tile_size
		# Calculate scale factor for proportional scaling
		scale_factor = float(TILE_SIZE) / REFERENCE_TILE_SIZE
		
		# Update dynamic values based on tile size
		# Player hitbox is 75% of tile size (12px at 16px tiles) for corridor clearance
		PLAYER_HALF_WIDTH = (TILE_SIZE * 0.75) / 2.0 # 6px at 16px tiles, 24px at 64px tiles
		
		# Saturn Bomberman base speed: 1 pixel/frame at 16px tile size
		# Scale proportionally: at 64px tiles, move 4 pixels/frame
		# Convert to pixels/second: pixels_per_frame * 60 fps
		BASE_SPEED = float(SATURN_BASE_PIXELS_PER_FRAME) * scale_factor * 60.0
		
		# Scale other movement speeds proportionally
		SNAP_TO_CENTER_SPEED = SNAP_TO_CENTER_SPEED_REFERENCE * scale_factor
		CORNER_ASSIST_THRESHOLD = CORNER_ASSIST_THRESHOLD_REFERENCE * scale_factor
		COLLISION_CHECK_DISTANCE = COLLISION_CHECK_DISTANCE_REFERENCE * scale_factor
		SNAP_THRESHOLD = 0.5 * scale_factor # Snap threshold scales too
		
		print("[GameConfig] Loaded TILE_SIZE: ", TILE_SIZE, "px (scale: ", scale_factor, "x)")
		print("[GameConfig] Saturn speed: ", SATURN_BASE_PIXELS_PER_FRAME, " px/frame @ 16px -> ", BASE_SPEED, " px/s @ ", TILE_SIZE, "px")
	
	if map_data.has("width"):
		map_width = map_data.width
	
	if map_data.has("height"):
		map_height = map_data.height
	
	if map_data.has("name"):
		map_name = map_data.name
	
	if map_data.has("spawn_points"):
		spawn_points = map_data.spawn_points
	
	print("[GameConfig] Map: ", map_name, " (", map_width, "x", map_height, ") Tile size: ", TILE_SIZE, "px, Player hitbox: ", PLAYER_HALF_WIDTH * 2, "px")

func reset_to_defaults():
	"""Reset to default values"""
	TILE_SIZE = 64
	scale_factor = float(TILE_SIZE) / REFERENCE_TILE_SIZE
	PLAYER_HALF_WIDTH = (TILE_SIZE * 0.75) / 2.0
	BASE_SPEED = float(SATURN_BASE_PIXELS_PER_FRAME) * scale_factor * 60.0
	SNAP_TO_CENTER_SPEED = SNAP_TO_CENTER_SPEED_REFERENCE * scale_factor
	CORNER_ASSIST_THRESHOLD = CORNER_ASSIST_THRESHOLD_REFERENCE * scale_factor
	COLLISION_CHECK_DISTANCE = COLLISION_CHECK_DISTANCE_REFERENCE * scale_factor
	SNAP_THRESHOLD = 0.5 * scale_factor
	map_width = 17
	map_height = 11
	map_name = "Unknown"
	spawn_points = []

## Calculate pixels to move this frame using Saturn Bomberman's accumulator model
## Returns: [pixels_to_move: int, new_accumulator: int]
func calculate_saturn_movement(skate_count: int, current_accumulator: int) -> Array:
	"""
	Saturn Bomberman Accumulator Algorithm:
	1. Start with base movement (1 pixel at 16px tiles, scaled at larger tiles)
	2. Add skate_count * 32 to accumulator
	3. If accumulator >= 256, move extra pixel and wrap
	4. Cap at max 2 pixels per frame (prevents collision tunneling)
	
	Returns [pixels_to_move, new_accumulator]
	"""
	var base_pixels: int = SATURN_BASE_PIXELS_PER_FRAME
	var pixels_to_move: int = base_pixels
	var accumulator: int = current_accumulator
	
	# Add speed from roller skates (capped at max skates)
	var effective_skates = mini(skate_count, SATURN_MAX_SKATES)
	var addend: int = effective_skates * SATURN_SKATE_INCREMENT
	
	accumulator += addend
	
	# Check for overflow - each overflow grants +1 pixel
	while accumulator >= SATURN_ACCUMULATOR_MAX:
		pixels_to_move += 1
		accumulator -= SATURN_ACCUMULATOR_MAX
	
	# Hard cap to prevent tunneling through 16px obstacles
	pixels_to_move = mini(pixels_to_move, SATURN_MAX_PIXELS_PER_FRAME)
	
	return [pixels_to_move, accumulator]

## Get the speed multiplier for a given number of roller skates
## This is the average speed increase over the base speed
func get_skate_speed_multiplier(skate_count: int) -> float:
	"""
	Calculate average speed multiplier for roller skate power-ups.
	Used for UI display and server speed_multiplier field.
	
	| Skates | Multiplier |
	|--------|------------|
	| 0      | 1.000      |
	| 1      | 1.125      |
	| 2      | 1.250      |
	| 3      | 1.375      |
	| 4      | 1.500      |
	| 5      | 1.625      |
	| 6      | 1.750      |
	| 7      | 1.875      |
	| 8      | 2.000      |
	"""
	var effective_skates = mini(skate_count, SATURN_MAX_SKATES)
	# Each skate adds 12.5% speed (32/256 = 0.125)
	return 1.0 + (effective_skates * 0.125)
