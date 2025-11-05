extends StaticBody2D
class_name ServerBomb

# Server-authoritative bomb
# Uses Godot's built-in collision system with exceptions

const Constants = preload("res://shared/constants.gd")

var bomb_id: String = ""
var owner_id: String = ""
var explosion_range: int = 2
var explosion_timer: float = Constants.BOMB_TIMER
var has_exploded := false

signal exploded(bomb)

func _ready():
	# Set collision layers: bombs on layer 3, collide with walls (1) only
	collision_layer = Constants.COLLISION_LAYER_BOMBS
	collision_mask = Constants.COLLISION_LAYER_WALLS
	
	# Set up collision shape
	var collision_shape = CollisionShape2D.new()
	var shape = RectangleShape2D.new()
	shape.size = Vector2(GameConfig.TILE_SIZE * 0.7, GameConfig.TILE_SIZE * 0.7)  # Slightly smaller than tile
	collision_shape.shape = shape
	add_child(collision_shape)
	
	# Center on tile
	var tile_pos = get_tile_position()
	position = Vector2(
		tile_pos.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
		tile_pos.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
	)

func _physics_process(delta):
	if has_exploded:
		return
	
	explosion_timer -= delta
	if explosion_timer <= 0:
		explode()

func get_tile_position() -> Vector2i:
	return Vector2i(
		int(floor(position.x / GameConfig.TILE_SIZE)),
		int(floor(position.y / GameConfig.TILE_SIZE))
	)

func explode():
	if has_exploded:
		return
	
	has_exploded = true
	exploded.emit(self)
	
	# Bomb will be removed by game manager after explosion processing
	queue_free()

func get_state() -> Dictionary:
	return {
		"bomb_id": bomb_id,
		"owner_id": owner_id,
		"position": {"x": position.x, "y": position.y},
		"timer": explosion_timer,
		"range": explosion_range
	}
