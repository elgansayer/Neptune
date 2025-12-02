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

const Constants = preload("res://shared/constants.gd")

enum PowerUpType {
	BOMB_INCREASE,    # +1 max bombs (Max: 10)
	RANGE_INCREASE,   # +1 explosion range (Max: 16 full screen)
	SPEED_INCREASE,   # Advances SpeedIndex through lookup table (Max: 8)
	BOMB_KICKER,      # Boolean: enables bomb displacement
	POWER_GLOVE,      # Boolean: enables bomb lifting/throwing
	VIRUS             # Curse: negative effects
}

var powerup_id: String = ""
var powerup_type: PowerUpType = PowerUpType.BOMB_INCREASE
var collected: bool = false
var destroyed: bool = false  # Destroyed by explosion

func _ready():
	# Set up collision detection
	collision_layer = Constants.COLLISION_LAYER_POWERUPS  # Layer 5 (bit 4)
	collision_mask = Constants.COLLISION_LAYER_PLAYERS    # Detect players
	
	# Create trigger zone collision shape
	# Per Saturn spec: 12x12 pixels centered in 16x16 tile = 75% of tile size
	var collision_shape = CollisionShape2D.new()
	var shape = RectangleShape2D.new()
	# Use rectangular shape for precise corner detection (not circle)
	var trigger_size = GameConfig.TILE_SIZE * Constants.POWERUP_TRIGGER_RATIO
	shape.size = Vector2(trigger_size, trigger_size)
	collision_shape.shape = shape
	add_child(collision_shape)
	
	# Connect collision signal
	body_entered.connect(_on_body_entered)

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
