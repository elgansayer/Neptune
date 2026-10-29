extends Node

# === Game Constants ===
const TILE_SIZE = 16  # 16px tiles for 320x224 viewport (Saturn Bomberman native)
const BASE_SPEED = 60.0  # Saturn Bomberman: 1 px/frame @ 16px tiles = 60 px/s
const PLAYER_HALF_WIDTH = 6.0  # 12x12 collision box (75% of 16px tile for corridor clearance)

# Collision Layers (physics layer bit positions)
const COLLISION_LAYER_WALLS = 1      # Layer 1 (bit 0): Solid/destructible walls
const COLLISION_LAYER_PLAYERS = 2    # Layer 2 (bit 1): Player characters
const COLLISION_LAYER_BOMBS = 4      # Layer 3 (bit 2): Bombs
const COLLISION_LAYER_EXPLOSIONS = 8 # Layer 4 (bit 3): Explosion damage areas
const COLLISION_LAYER_POWERUPS = 16  # Layer 5 (bit 4): Power-up items

# Canvas layering for consistent draw order (higher values render above lower ones)
# Per Saturn Bomberman spec:
# - Layer 0: Background (arena floor)
# - Layer 1: Shadows (flat on ground, unifies depth)
# - Layer 2: Items (NOT Y-sorted with players - "flat" on ground)
# - Layer 3: Dynamic entities (players, bombs, tirras) with Y-sort enabled
const Z_LAYERS = {
	"FLOOR": -100,
	"SHADOW": -50,           # Shadows render on floor below items
	"SOFT_BLOCK": -40,
	"POWERUP": -20,          # Items are "flat" on the ground (below players)
	"BOMB": -10,
	"SOFT_BLOCK_EFFECT": 5,
	"EXPLOSION": 10,
	"PLAYER_BASE": 100,      # Players always above floor items
	"PLAYER_STEP": 1,
	"UI": 1000
}

# === Saturn Bomberman Stat Limits (from competitive spec) ===
# These define the min/max values for player stats

# Bomb Count: How many bombs player can have deployed at once
const BOMB_MIN: int = 1
const BOMB_MAX: int = 10
const BOMB_DEFAULT: int = 1

# Fire Range: Explosion radius in tiles
const FIRE_MIN: int = 1
const FIRE_MAX: int = 8       # Normal maximum (with Fire Up items)
const FIRE_MAX_FULL: int = 16 # With Full Fire item (covers entire arena)
const FIRE_DEFAULT: int = 2

# Speed Level: Index into speed lookup table
const SPEED_MIN: int = 1
const SPEED_MAX: int = 8
const SPEED_DEFAULT: int = 1

# === Saturn Bomberman Pickup Mechanics (from spec) ===
# Trigger zone matches full tile size for easier collection
# Scaled to current TILE_SIZE
const POWERUP_TRIGGER_RATIO: float = 1.0  # Full tile size

# Player Anchor: Single pixel at center-bottom of player sprite
# Used for point-in-rect pickup detection (not AABB collision)
# This prevents "corner snagging" during movement

# Speed Lookup Table (from spec section 4.1)
# Speed Up item advances player through this table (not linear float)
const SPEED_LEVELS = [
	0.5,   # Level 0 (Curse): Sluggish
	1.0,   # Level 1 (Default)
	1.5,   # Level 2
	2.0,   # Level 3
	2.5,   # Level 4
	3.0,   # Level 5
	3.5,   # Level 6
	4.0,   # Level 7
	4.0    # Level 8 (Max): Hyper-speed
]

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

# Power-up Drop Rates (from soft block destruction)
# Chance that a soft block drops ANY powerup when destroyed
const POWERUP_DROP_CHANCE: float = 0.30  # 30% base chance

# Weighted distribution of powerup types (must sum to 1.0)
# These weights determine which type spawns WHEN a drop occurs
# Saturn Bomberman distribution - common items are more frequent
const POWERUP_WEIGHTS = {
	"BOMB_UP": 0.18,       # Extra bomb capacity
	"FIRE_UP": 0.18,       # Increased explosion range  
	"SPEED_UP": 0.15,      # Movement speed boost
	"FULL_FIRE": 0.04,     # Max explosion range (rare)
	"BOMB_KICK": 0.08,     # Kick bombs ability
	"POWER_GLOVE": 0.08,   # Pick up/throw bombs
	"RUBBER_BOMB": 0.06,   # Bouncing bombs
	"PENETRATION_BOMB": 0.04, # Explosions pass through soft blocks
	"LINE_BOMB": 0.00,     # Place all bombs in a line (disabled)
	"SKULL": 0.065,        # Virus/curse effect
	"HEART": 0.065,        # Extra life (battle mode)
	"1UP": 0.02,           # Extra continue
	"CLOCK": 0.03,         # Time bonus
	"EGG": 0.02            # Louie mount (rare)
}

# Network
const SERVER_PORT = 7777
const MAX_MATCH_SEATS = 12 # Application protocol capacity, independent of presets.
const MAX_CONNECTED_PEERS = 16 # Includes peers waiting outside the shared room.
const MAX_PLAYERS = MAX_MATCH_SEATS # Compatibility alias; not the transport limit.
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
