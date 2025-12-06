extends Node2D
class_name ClientPlayer

## Client-side player visual representation
## Uses scene-based structure for easier editing and debugging

@onready var sprite_container: Node2D = $SpriteContainer
@onready var debug_arrow: Polygon2D = $DebugArrow
@onready var hitbox_visual: Line2D = $HitboxVisual
@onready var raycast_line: Line2D = $RaycastLine
@onready var shapecast_visual: Line2D = $ShapeCastVisual
@onready var target_debug_line: Line2D = $TargetDebugLine

var peer_id: String = ""
var animated_sprite: AnimatedSprite2D = null
var is_local_player: bool = false

func _ready():
	# Initialize hitbox visual as a square based on GameConfig
	_setup_hitbox_visual()

func _setup_hitbox_visual():
	"""Draw the player hitbox as a rectangle"""
	var half_size = GameConfig.PLAYER_HALF_WIDTH
	hitbox_visual.clear_points()
	hitbox_visual.add_point(Vector2(-half_size, -half_size))
	hitbox_visual.add_point(Vector2(half_size, -half_size))
	hitbox_visual.add_point(Vector2(half_size, half_size))
	hitbox_visual.add_point(Vector2(-half_size, half_size))
	hitbox_visual.add_point(Vector2(-half_size, -half_size))

func setup_sprite(player_scene: PackedScene = null):
	"""Set up the player sprite from a PackedScene or use fallback"""
	# Clear existing children in sprite container
	for child in sprite_container.get_children():
		child.queue_free()
	
	if player_scene:
		var sprite_root = player_scene.instantiate()
		sprite_root.position = Vector2.ZERO
		sprite_container.add_child(sprite_root)
		
		# Find AnimatedSprite2D
		animated_sprite = sprite_root.get_node_or_null("AnimatedSprite2D")
		if animated_sprite:
			animated_sprite.play("state_idle")
	else:
		# Fallback to colored rectangle
		var sprite = ColorRect.new()
		var sprite_size = GameConfig.TILE_SIZE / 2.0
		sprite.size = Vector2(sprite_size, sprite_size)
		sprite.position = Vector2(-sprite_size / 2, -sprite_size / 2)
		sprite.color = Color(0.2, 0.6, 1.0) if is_local_player else Color(1.0, 0.3, 0.3)
		sprite_container.add_child(sprite)

func set_facing(facing: String):
	"""Update debug arrow rotation based on facing direction"""
	var rotation_map = {
		"RIGHT": 0.0,
		"DOWN": PI / 2.0,
		"LEFT": PI,
		"UP": -PI / 2.0
	}
	if facing in rotation_map:
		debug_arrow.rotation = rotation_map[facing]

func play_animation(anim_name: String):
	"""Play a specific animation if available"""
	if animated_sprite and animated_sprite.sprite_frames.has_animation(anim_name):
		animated_sprite.play(anim_name)
	elif animated_sprite and animated_sprite.sprite_frames.has_animation("state_idle"):
		animated_sprite.play("state_idle")

func update_target_line(points: PackedVector2Array):
	"""Update the target debug line"""
	if points.size() >= 2:
		target_debug_line.visible = true
		target_debug_line.clear_points()
		for p in points:
			target_debug_line.add_point(to_local(p))
	else:
		target_debug_line.visible = false
		target_debug_line.clear_points()

func show_death_animation():
	"""Trigger death animation if available"""
	if animated_sprite and animated_sprite.sprite_frames.has_animation("state_defeat"):
		animated_sprite.play("state_defeat")
		return true
	return false

# === IMMORTALITY FLASH EFFECT (Saturn Bomberman style) ===
# When is_immortal and flash_white is true, player flashes white

var _last_flash_state: bool = false

func set_immortal_flash(flash_white: bool, is_immortal: bool) -> void:
	"""Set the immortality flash state for Saturn Bomberman style invincibility.
	flash_white toggles every ~100ms while is_immortal is true."""
	if not is_immortal:
		# Restore normal appearance
		if _last_flash_state:
			_set_white_modulate(false)
			_last_flash_state = false
		return
	
	# Only update if flash state changed
	if flash_white != _last_flash_state:
		_set_white_modulate(flash_white)
		_last_flash_state = flash_white

func _set_white_modulate(white: bool) -> void:
	"""Apply white flash to the player sprite."""
	# Use modulate on the sprite container for the flash effect
	# White = bright, colorless; Normal = Color.WHITE (no tint)
	if white:
		# Flash bright white by adding to the color (makes it look washed out/invincible)
		sprite_container.modulate = Color(2.5, 2.5, 2.5, 1.0)  # Bright white flash
	else:
		sprite_container.modulate = Color.WHITE  # Normal appearance

func set_flying_visual(is_flying: bool) -> void:
	"""Visual indication of arc jump (flying through air)."""
	# Could add shadow, height offset, or scale effect
	if is_flying:
		# Slight scale increase to indicate height
		sprite_container.scale = Vector2(1.1, 1.1)
	else:
		sprite_container.scale = Vector2.ONE
