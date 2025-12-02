extends Node2D
class_name HurryBlockShadow
## Shadow that appears before a hurry block falls
## Authentic SNES Super Bomberman 2 timing: appears 60 frames (1 second) before impact
##
## Uses the shadow.png asset from res/items/sbomberman/shadow.png

# === SNES-ACCURATE TIMING ===
# Shadow appears 60 frames (1.0 second @ 60 FPS) before block lands
# Block takes 22 frames to fall (at 12 pixels/frame)
# Total warning time: 82 frames = ~1.37 seconds

signal shadow_warning_complete  # Emitted after 60 frames, time for block to start falling

const SHADOW_WARNING_FRAMES := 60  # 1.0 second at 60 FPS
const SHADOW_WARNING_SECONDS := 1.0

# Pulsing animation parameters (SNES-authentic)
const PULSE_SCALE_START := 0.8
const PULSE_SCALE_PEAK := 1.2
const PULSE_SCALE_FINAL := 1.0

var target_tile: Vector2i
var is_warning_complete := false

# ShadowSprite is defined in HurryBlockShadow.tscn
@onready var shadow_sprite: Sprite2D = $ShadowSprite

func _ready():
	# z_index is already set in HurryBlockShadow.tscn
	_setup_shadow_visual()
	_start_warning_animation()

func _setup_shadow_visual():
	"""Set up shadow sprite from scene - scale to match tile size"""
	if shadow_sprite and shadow_sprite.texture:
		# Scale to match tile size
		var tex_size = shadow_sprite.texture.get_size()
		var tile_size = GameConfig.TILE_SIZE
		shadow_sprite.scale = Vector2(tile_size / tex_size.x, tile_size / tex_size.y) * 0.9
	else:
		# Fallback: create procedural shadow if texture missing
		_create_procedural_shadow()
	
	# Start invisible and small
	shadow_sprite.modulate = Color(1, 1, 1, 0)
	shadow_sprite.scale *= PULSE_SCALE_START

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
	shadow_sprite.scale = Vector2(tile_size / 32.0, tile_size / 32.0)

func _start_warning_animation():
	"""Animate the shadow with SNES-authentic timing:
	   - Fade in from 0 to 1 alpha
	   - Pulse scale: 0.8 -> 1.2 -> 1.0
	   - Emit signal after 60 frames (1.0 second)"""
	
	var base_scale = shadow_sprite.scale
	
	# Phase 1: Fade in + expand (first 0.3 seconds)
	var tween1 = create_tween()
	tween1.set_parallel(true)
	tween1.tween_property(shadow_sprite, "modulate:a", 1.0, 0.3).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tween1.tween_property(shadow_sprite, "scale", base_scale / PULSE_SCALE_START * PULSE_SCALE_PEAK, 0.4).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	
	# Phase 2: Settle to final scale
	await tween1.finished
	var tween2 = create_tween()
	tween2.tween_property(shadow_sprite, "scale", base_scale / PULSE_SCALE_START * PULSE_SCALE_FINAL, 0.6).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	
	# Wait for total warning duration then emit signal
	# We've used ~0.4 + 0.6 = 1.0 second, which matches SHADOW_WARNING_SECONDS
	await tween2.finished
	
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
