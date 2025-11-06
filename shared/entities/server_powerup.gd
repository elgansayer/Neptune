extends Area2D
class_name ServerPowerUp

# Server-side power-up entity
# Spawns on block destruction and increases player stats

const Constants = preload("res://shared/constants.gd")

enum PowerUpType {
	BOMB_INCREASE,    # +1 max bombs
	RANGE_INCREASE,   # +1 explosion range  
	SPEED_INCREASE,   # +movement speed
	BOMB_KICKER,      # Ability to kick bombs (Phase 2)
	POWER_GLOVE,      # Ability to pick up/throw bombs (Phase 2)
	VIRUS             # Negative powerup (Phase 2 - multiple variants)
}

var powerup_id: String = ""
var powerup_type: PowerUpType = PowerUpType.BOMB_INCREASE
var collected: bool = false
var destroyed: bool = false  # Destroyed by explosion

func _ready():
	# Set up collision detection
	collision_layer = Constants.COLLISION_LAYER_POWERUPS  # Layer 4
	collision_mask = Constants.COLLISION_LAYER_PLAYERS    # Detect players
	
	# Create circular collision shape
	var collision_shape = CollisionShape2D.new()
	var shape = CircleShape2D.new()
	shape.radius = GameConfig.TILE_SIZE / 3.0  # Smaller than tile
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
