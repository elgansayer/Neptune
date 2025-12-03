extends Node2D
class_name HurryBlockShadow
## Shadow that appears before a hurry block falls
## Authentic SNES Super Bomberman 2 timing: appears 60 frames (1 second) before impact
##
## Uses the shadow.png asset from res/items/sbomberman/shadow.png
## Animation is defined in the editor via AnimationPlayer

# === SNES-ACCURATE TIMING ===
# Shadow appears 60 frames (1.0 second @ 60 FPS) before block lands
# Block takes 22 frames to fall (at 12 pixels/frame)
# Total warning time: 82 frames = ~1.37 seconds

signal shadow_warning_complete  # Emitted after animation finishes, time for block to start falling

const SHADOW_WARNING_SECONDS := 1.0

var target_tile: Vector2i
var is_warning_complete := false

# Nodes defined in HurryBlockShadow.tscn
@onready var shadow_sprite: Sprite2D = $ShadowSprite
@onready var anim_player: AnimationPlayer = $AnimationPlayer

func _ready():
	_setup_shadow_visual()
	_start_warning_animation()

func _setup_shadow_visual():
	"""Set up shadow sprite - scale to match tile size"""
	if shadow_sprite and shadow_sprite.texture:
		# Scale to match tile size (base animation uses 0.9 scale factor)
		var tex_size = shadow_sprite.texture.get_size()
		var tile_size = GameConfig.TILE_SIZE
		var base_scale = (tile_size / tex_size.x) * 0.9
		# Update the animation's scale values proportionally
		shadow_sprite.scale = Vector2(base_scale * 0.8, base_scale * 0.8)  # Start at 0.8x
	else:
		# Fallback: create procedural shadow if texture missing
		_create_procedural_shadow()

func _create_procedural_shadow():
	"""Create a procedural elliptical shadow if texture not found"""
	var image = Image.create(32, 32, false, Image.FORMAT_RGBA8)
	image.fill(Color(0, 0, 0, 0))
	
	var center = Vector2(16, 16)
	var radius_x = 14.0
	var radius_y = 10.0
	
	for x in range(32):
		for y in range(32):
			var dx = (x - center.x) / radius_x
			var dy = (y - center.y) / radius_y
			var dist = sqrt(dx * dx + dy * dy)
			if dist <= 1.0:
				var alpha = clampf(1.0 - dist * 0.5, 0.0, 1.0) * 0.6
				image.set_pixel(x, y, Color(0, 0, 0, alpha))
	
	var texture = ImageTexture.create_from_image(image)
	shadow_sprite.texture = texture
	
	var tile_size = GameConfig.TILE_SIZE
	shadow_sprite.scale = Vector2(tile_size / 32.0, tile_size / 32.0) * 0.8

func _start_warning_animation():
	"""Play the warning animation defined in AnimationPlayer"""
	if anim_player and anim_player.has_animation("warning"):
		# Calculate scale values for current tile size
		if shadow_sprite and shadow_sprite.texture:
			var tex_size = shadow_sprite.texture.get_size()
			var tile_size = GameConfig.TILE_SIZE
			var base_scale = (tile_size / tex_size.x) * 0.9
			# Animation goes: 0.8x -> 1.2x -> 1.0x of base_scale
			shadow_sprite.scale = Vector2(base_scale * 0.8, base_scale * 0.8)
		anim_player.play("warning")
	else:
		# Fallback if no animation player - just emit signal after delay
		await get_tree().create_timer(SHADOW_WARNING_SECONDS).timeout
		_on_animation_finished("warning")

func _on_animation_finished(anim_name: StringName):
	"""Called when warning animation completes"""
	if anim_name == "warning":
		is_warning_complete = true
		shadow_warning_complete.emit()

func set_target_tile(tile: Vector2i):
	"""Position the shadow on the target tile"""
	target_tile = tile
	position = Vector2(
		tile.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
		tile.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
	)

func hide_shadow():
	"""Hide shadow when block lands (called by FallingHurryBlock)"""
	if shadow_sprite:
		shadow_sprite.visible = false

func cleanup():
	"""Remove the shadow from scene"""
	queue_free()
