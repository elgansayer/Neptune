extends Node

## GameConfig - Runtime game configuration loaded from map metadata
## This replaces hardcoded constants with values from the active map

# === MAP-DEPENDENT VALUES (loaded from map metadata) ===
var TILE_SIZE: int = 64 # Default, overridden by map metadata
var map_width: int = 17
var map_height: int = 11
var map_name: String = "Unknown"
var spawn_points: Array = []

# === DYNAMIC SCALING (computed from TILE_SIZE) ===
# Reference tile size: 16px (native pixel art size)
const REFERENCE_TILE_SIZE = 16.0
var scale_factor: float = 1.0 # TILE_SIZE / REFERENCE_TILE_SIZE

# === STATIC CONSTANTS (scaled proportionally) ===
# Base values are defined for 16px reference tile size
const BASE_SPEED_REFERENCE = 90.0 # Speed at 16px tile size (Saturn Bomberman: ~90 px/s)
const SNAP_TO_CENTER_SPEED_REFERENCE = 60.0 # Snap speed at 16px tile size (increased for better alignment)
const CORNER_ASSIST_THRESHOLD_REFERENCE = 5.0 # Corner assist at 16px tile size
const COLLISION_CHECK_DISTANCE_REFERENCE = 2.0 # Collision check distance at 16px tile size

# === SATURN PHYSICS CONSTANTS ===
const ACCELERATION_RATE = 12.0 # Saturn Bomberman's subtle acceleration ramp-up
const SPEED_LEVEL_INCREMENT = 0.125 # +12.5% per speed upgrade (Saturn Roller Skates)
const MAX_SPEED_LEVEL = 7 # Maximum speed upgrades (0-7 levels)

# PLAYER_HALF_WIDTH is dynamic: always TILE_SIZE / 2
# This ensures collision boxes always match the tile grid
var PLAYER_HALF_WIDTH: float = 32.0 # Default for 64px tiles, updated in load_map_config()

# Scaled values (computed in load_map_config)
var BASE_SPEED: float = 180.0 # BASE_SPEED_REFERENCE * scale_factor
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
		# Player is 87.5% of tile size (56/64 = 0.875) to allow clearance
		PLAYER_HALF_WIDTH = (TILE_SIZE * 0.875) / 2.0 # 7px at 16px tiles, 28px at 64px tiles
		
		# Scale movement speeds proportionally
		BASE_SPEED = BASE_SPEED_REFERENCE * scale_factor
		SNAP_TO_CENTER_SPEED = SNAP_TO_CENTER_SPEED_REFERENCE * scale_factor
		CORNER_ASSIST_THRESHOLD = CORNER_ASSIST_THRESHOLD_REFERENCE * scale_factor
		COLLISION_CHECK_DISTANCE = COLLISION_CHECK_DISTANCE_REFERENCE * scale_factor
		SNAP_THRESHOLD = 0.5 * scale_factor # Snap threshold scales too
		
		print("[GameConfig] Loaded TILE_SIZE: ", TILE_SIZE, "px (scale: ", scale_factor, "x)")
		print("[GameConfig] Scaled BASE_SPEED: ", BASE_SPEED, " px/s")
	
	if map_data.has("width"):
		map_width = map_data.width
	
	if map_data.has("height"):
		map_height = map_data.height
	
	if map_data.has("name"):
		map_name = map_data.name
	
	if map_data.has("spawn_points"):
		spawn_points = map_data.spawn_points
	
	print("[GameConfig] Map: ", map_name, " (", map_width, "x", map_height, ") Tile size: ", TILE_SIZE, "px, Player size: ", PLAYER_HALF_WIDTH * 2, "px")

func reset_to_defaults():
	"""Reset to default values"""
	TILE_SIZE = 64
	scale_factor = float(TILE_SIZE) / REFERENCE_TILE_SIZE
	PLAYER_HALF_WIDTH = (TILE_SIZE * 0.875) / 2.0
	BASE_SPEED = BASE_SPEED_REFERENCE * scale_factor
	SNAP_TO_CENTER_SPEED = SNAP_TO_CENTER_SPEED_REFERENCE * scale_factor
	CORNER_ASSIST_THRESHOLD = CORNER_ASSIST_THRESHOLD_REFERENCE * scale_factor
	COLLISION_CHECK_DISTANCE = COLLISION_CHECK_DISTANCE_REFERENCE * scale_factor
	SNAP_THRESHOLD = 0.5 * scale_factor
	map_width = 17
	map_height = 11
	map_name = "Unknown"
	spawn_points = []
