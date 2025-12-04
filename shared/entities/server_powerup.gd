extends Area2D
class_name ServerPowerUp

## Server-side power-up entity
## Spawns on block destruction and increases player stats
##
## === Saturn Bomberman Pickup Physics (from spec) ===
## Tile Size: 16x16 logical units (scaled to GameConfig.TILE_SIZE)
## Trigger Zone: 12x12 pixels centered in the tile (75% of tile)
## Player Anchor: Single pixel at center-bottom of player sprite
## Interaction Rule: if (TriggerRect.has_point(PlayerAnchor)): Collect()
##
## This model ensures a player must commit to entering the tile to 
## trigger the pickup. A player moving perpendicularly along the edge 
## (grazing the outer 2 pixels) will NOT trigger collection.
##
## === Saturn Bomberman Item Types ===
## Common Items (always drop):
##   Bomb Up:    +1 bomb capacity (max 10)
##   Fire Up:    +1 fire range (max 8, or 16 with Full Fire)
##   Speed Up:   +1 speed level (max 8)
##
## Rare Items (uncommon drops):
##   Geta:       -1 speed level (negative item!)
##   Full Fire:  Fire range set to max (16 tiles)
##   Heart:      Extra life (competitive mode)
##
## Special Abilities (rare drops):
##   Bomb Kick:  Can kick bombs by walking into them
##   Power Glove: Can pick up and throw bombs
##   Line Bomb:  Place all bombs in a line
##
## Bomb Type Items (change bomb behavior):
##   Remote Bomb: Manual detonation
##   Power Bomb:  Pierces through soft blocks
##   Rubber Bomb: Bounces off walls
##   Pierce Bomb: (alias for Power Bomb in some versions)
##
## Negative Items:
##   Skull:      Apply random curse effect

const Constants = preload("res://shared/constants.gd")

## Power-up types matching Saturn Bomberman item set
## NOTE: Enum values are used for network sync and must remain stable
enum PowerUpType {
	# Common stat items (0-2)
	BOMB_INCREASE = 0,    # +1 max bombs (Max: 10)
	RANGE_INCREASE = 1,   # +1 explosion range (Max: 8 or 16 with Full Fire)
	SPEED_INCREASE = 2,   # +1 speed level (Max: 8)
	
	# Ability items (3-5)
	BOMB_KICKER = 3,      # Boolean: enables bomb displacement
	POWER_GLOVE = 4,      # Boolean: enables bomb lifting/throwing
	LINE_BOMB = 5,        # Boolean: place all bombs in a line
	
	# Special items (6-8)
	FULL_FIRE = 6,        # Set fire range to max (16)
	HEART = 7,            # Extra life
	GETA = 8,             # Slow shoes: -1 speed (negative item!)
	
	# Bomb type changers (9-12)
	REMOTE_BOMB = 9,      # Manual detonation bombs
	POWER_BOMB = 10,      # Piercing bombs (through soft blocks)
	RUBBER_BOMB = 11,     # Bouncing bombs
	PIERCE_BOMB = 12,     # Alias for Power Bomb (some versions)
	
	# Negative items (13+)
	SKULL = 13,           # Random curse effect (was VIRUS)
	
	# Legacy alias
	VIRUS = 13            # Deprecated: use SKULL instead
}

var powerup_id: String = ""
var powerup_type: PowerUpType = PowerUpType.BOMB_INCREASE
var collected: bool = false
var destroyed: bool = false  # Destroyed by explosion

# Collision shape is defined in ServerPowerUp.tscn
@onready var collision_shape: CollisionShape2D = $CollisionShape2D

func _ready():
	# Collision layers are already set in ServerPowerUp.tscn
	# Update collision shape size to match current GameConfig values
	_update_collision_shape_size()
	
	# Ensure monitoring is enabled (required for body_entered signal)
	monitoring = true
	monitorable = false  # We don't need other areas to detect us
	
	# Connect collision signal
	body_entered.connect(_on_body_entered)

func _update_collision_shape_size():
	"""Update collision shape to match current GameConfig values"""
	if collision_shape and collision_shape.shape:
		var trigger_size = GameConfig.TILE_SIZE * Constants.POWERUP_TRIGGER_RATIO
		collision_shape.shape.size = Vector2(trigger_size, trigger_size)

func _on_body_entered(body):
	if collected or destroyed:
		return
	
	# Check if it's a player
	if body.has_method("collect_powerup"):
		collected = true
		body.collect_powerup(self)
		# Power-up will be removed by GameInstance
		emit_signal("powerup_collected", self)

func destroy():
	"""Called when powerup is destroyed by explosion"""
	if collected or destroyed:
		return
	
	destroyed = true
	# Emit signal for visual effect (smoke animation on client)
	emit_signal("powerup_destroyed", self)
	# Will be removed by GameInstance

signal powerup_destroyed(powerup)

func get_tile_position() -> Vector2i:
	return Vector2i(
		int(floor(position.x / GameConfig.TILE_SIZE)),
		int(floor(position.y / GameConfig.TILE_SIZE))
	)

func get_state() -> Dictionary:
	return {
		"powerup_id": powerup_id,
		"type": powerup_type,
		"position": {"x": position.x, "y": position.y}
	}

signal powerup_collected(powerup)

## Get the animation name for this powerup type (used by renderer)
static func get_animation_name(type: PowerUpType) -> String:
	match type:
		PowerUpType.BOMB_INCREASE:
			return "bomb"
		PowerUpType.RANGE_INCREASE:
			return "fire"
		PowerUpType.SPEED_INCREASE:
			return "skate"
		PowerUpType.BOMB_KICKER:
			return "kickbomb"
		PowerUpType.POWER_GLOVE:
			return "pglove"
		PowerUpType.LINE_BOMB:
			return "line_bomb"
		PowerUpType.FULL_FIRE:
			return "full_fire"
		PowerUpType.HEART:
			return "heart"
		PowerUpType.GETA:
			return "geta"
		PowerUpType.REMOTE_BOMB:
			return "remote_bomb"
		PowerUpType.POWER_BOMB, PowerUpType.PIERCE_BOMB:
			return "power_bomb"
		PowerUpType.RUBBER_BOMB:
			return "rubber_bomb"
		PowerUpType.SKULL, PowerUpType.VIRUS:
			return "skull"
		_:
			return "bomb"

## Check if this powerup type is a negative item
static func is_negative_item(type: PowerUpType) -> bool:
	return type in [PowerUpType.SKULL, PowerUpType.VIRUS, PowerUpType.GETA]

## Check if this powerup type changes bomb behavior
static func is_bomb_type_changer(type: PowerUpType) -> bool:
	return type in [
		PowerUpType.REMOTE_BOMB,
		PowerUpType.POWER_BOMB,
		PowerUpType.RUBBER_BOMB,
		PowerUpType.PIERCE_BOMB
	]

## Get a human-readable name for the powerup type
static func get_display_name(type: PowerUpType) -> String:
	match type:
		PowerUpType.BOMB_INCREASE:
			return "Bomb Up"
		PowerUpType.RANGE_INCREASE:
			return "Fire Up"
		PowerUpType.SPEED_INCREASE:
			return "Speed Up"
		PowerUpType.BOMB_KICKER:
			return "Bomb Kick"
		PowerUpType.POWER_GLOVE:
			return "Power Glove"
		PowerUpType.LINE_BOMB:
			return "Line Bomb"
		PowerUpType.FULL_FIRE:
			return "Full Fire"
		PowerUpType.HEART:
			return "Heart"
		PowerUpType.GETA:
			return "Slow Shoes"
		PowerUpType.REMOTE_BOMB:
			return "Remote Bomb"
		PowerUpType.POWER_BOMB, PowerUpType.PIERCE_BOMB:
			return "Power Bomb"
		PowerUpType.RUBBER_BOMB:
			return "Rubber Bomb"
		PowerUpType.SKULL, PowerUpType.VIRUS:
			return "Skull"
		_:
			return "Unknown"
