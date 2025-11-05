extends Node

## GameConfig - Runtime game configuration loaded from map metadata
## This replaces hardcoded constants with values from the active map

# === MAP-DEPENDENT VALUES (loaded from map metadata) ===
var TILE_SIZE: int = 64  # Default, overridden by map metadata
var map_width: int = 17
var map_height: int = 11
var map_name: String = "Unknown"
var spawn_points: Array = []

# === STATIC CONSTANTS (never change) ===
const BASE_SPEED = 180.0
const PLAYER_HALF_WIDTH = 28.0  # 56x56 collision box

# Collision Layers (physics layer bit positions)
const COLLISION_LAYER_WALLS = 1      # Layer 1 (bit 0): Solid/destructible walls
const COLLISION_LAYER_PLAYERS = 2    # Layer 2 (bit 1): Player characters
const COLLISION_LAYER_BOMBS = 4      # Layer 3 (bit 2): Bombs
const COLLISION_LAYER_EXPLOSIONS = 8 # Layer 4 (bit 3): Explosion damage areas
const COLLISION_LAYER_POWERUPS = 16  # Layer 5 (bit 4): Power-up items

# Movement
const WALK_MULTIPLIER = 0.6
const RUN_MULTIPLIER = 1.0
const WALK_RUN_THRESHOLD = 0.5
const INPUT_DEADZONE = 0.1

# Grid alignment
const SNAP_TO_CENTER_SPEED = 120.0
const SNAP_THRESHOLD = 2.0

# Cornering
const CORNER_ASSIST_THRESHOLD = 20
const CORNER_ASSIST_SPEED_MULTIPLIER = 0.8

# Bomb
const BOMB_TIMER = 3.0
const EXPLOSION_DURATION = 1.0
const DEFAULT_BOMB_RANGE = 2

# Network
const SERVER_PORT = 7777
const MAX_PLAYERS = 8
const TICK_RATE = 60  # Server physics runs at 60 FPS
const NETWORK_SEND_RATE = 20  # Send state updates 20 times per second

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
		print("[GameConfig] Loaded TILE_SIZE: ", TILE_SIZE)
	
	if map_data.has("width"):
		map_width = map_data.width
	
	if map_data.has("height"):
		map_height = map_data.height
	
	if map_data.has("name"):
		map_name = map_data.name
	
	if map_data.has("spawn_points"):
		spawn_points = map_data.spawn_points
	
	print("[GameConfig] Map: ", map_name, " (", map_width, "x", map_height, ") Tile size: ", TILE_SIZE, "px")

func reset_to_defaults():
	"""Reset to default values"""
	TILE_SIZE = 64
	map_width = 17
	map_height = 11
	map_name = "Unknown"
	spawn_points = []
