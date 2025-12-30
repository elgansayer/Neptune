extends Area2D
class_name BaseCollectable

## Base class for all collectables (powerups, eggs, etc.)
## Handles dynamic collision sizing and common collection logic
##
## === Saturn Bomberman Pickup Physics ===
## All collectables use tile-based collision detection
## Size automatically scales with GameConfig.TILE_SIZE

## Ratio of tile size for collision trigger (0.0-1.0)
## Override in child scenes via Inspector for different sizes
@export_range(0.1, 1.0) var trigger_size_ratio: float = 1.0

## Whether this has been collected (prevents double pickup)
var collected: bool = false

## Whether this has been destroyed by explosion
var destroyed: bool = false

# Reference to collision shape (defined in scene)
@onready var collision_shape: CollisionShape2D = $CollisionShape2D

signal collectable_collected(collectable)
signal collectable_destroyed(collectable)

func _ready():
	# Update collision shape to match current GameConfig values
	print("[BaseCollectable] _ready() - TILE_SIZE=", GameConfig.TILE_SIZE, 
	      " ratio=", trigger_size_ratio, " type=", get_class())
	_update_collision_shape_size()
	
	# Ensure monitoring is enabled
	monitoring = true
	monitorable = false  # We detect players, not vice versa
	
	# Connect collision signal
	body_entered.connect(_on_body_entered)

func _update_collision_shape_size():
	"""Update collision shape to match current GameConfig values"""
	if collision_shape and collision_shape.shape:
		var trigger_size = GameConfig.TILE_SIZE * trigger_size_ratio
		collision_shape.shape.size = Vector2(trigger_size, trigger_size)
		print("[BaseCollectable] Collision updated: ", trigger_size, "x", trigger_size,
		      " (TILE_SIZE=", GameConfig.TILE_SIZE, ", ratio=", trigger_size_ratio, ")")

func _on_body_entered(body: Node):
	"""Called when something enters the trigger area"""
	if collected or destroyed:
		return
	
	# Call overridable method for collection logic
	if _can_be_collected_by(body):
		_collect(body)

func _can_be_collected_by(body: Node) -> bool:
	"""Override in child classes to add custom collection rules"""
	return body.has_method("collect_powerup") or body.has_method("collect_item")

func _collect(body: Node):
	"""Handle collection - override in child classes for specific behavior"""
	collected = true
	emit_signal("collectable_collected", self)
	# Child classes should call their specific collection method

func destroy():
	"""Called when collectable is destroyed by explosion"""
	if collected or destroyed:
		return
	
	destroyed = true
	emit_signal("collectable_destroyed", self)
	# Will be removed by GameInstance

func get_tile_position() -> Vector2i:
	"""Get the tile coordinates of this collectable"""
	return Vector2i(
		int(floor(position.x / GameConfig.TILE_SIZE)),
		int(floor(position.y / GameConfig.TILE_SIZE))
	)
