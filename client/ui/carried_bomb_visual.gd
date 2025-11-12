extends Node2D
class_name CarriedBombVisual

# Visual attachment for bombs being carried by players
# Renders bomb at player's "overhead" position with offset

const OVERHEAD_OFFSET := Vector2(0, -40)  # Y offset above player's center
const BOB_AMPLITUDE := 3.0  # Vertical bobbing amount in pixels
const BOB_FREQUENCY := 3.0  # Bobbing cycles per second

var bomb_id: String = ""
var carrier: Node = null
var time_carried: float = 0.0

func _ready():
	z_index = 200  # Render above player

func _process(delta):
	time_carried += delta
	
	# Update position to follow carrier
	if is_instance_valid(carrier):
		# Calculate bobbing offset
		var bob_offset = sin(time_carried * BOB_FREQUENCY * TAU) * BOB_AMPLITUDE
		
		# Position relative to carrier with bobbing
		position = carrier.position + OVERHEAD_OFFSET + Vector2(0, bob_offset)
	else:
		# Carrier gone - remove visual
		queue_free()

func attach_to_carrier(bomb: Node, player: Node):
	"""Attach this visual to a player carrying a bomb"""
	bomb_id = bomb.bomb_id if bomb.has("bomb_id") else ""
	carrier = player
	time_carried = 0.0
	
	# Copy bomb's visual appearance
	if bomb.has_node("Sprite2D"):
		var bomb_sprite = bomb.get_node("Sprite2D")
		var our_sprite = Sprite2D.new()
		our_sprite.texture = bomb_sprite.texture
		our_sprite.scale = bomb_sprite.scale
		add_child(our_sprite)
	else:
		# Fallback: simple colored circle
		_create_fallback_visual()

func _create_fallback_visual():
	"""Create a simple visual if no sprite available"""
	var circle = Polygon2D.new()
	var points = PackedVector2Array()
	var segments = 16
	var radius = GameConfig.TILE_SIZE * 0.3
	
	for i in range(segments):
		var angle = (float(i) / segments) * TAU
		points.append(Vector2(cos(angle), sin(angle)) * radius)
	
	circle.polygon = points
	circle.color = Color(0.2, 0.2, 0.2)  # Dark gray bomb
	add_child(circle)

func detach():
	"""Remove the visual (bomb was thrown or dropped)"""
	queue_free()
