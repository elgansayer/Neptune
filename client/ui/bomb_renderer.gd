extends Node2D
class_name BombRenderer

## Client-side bomb visual with animations from SBomberman
## Handles 6-frame animation (3 idle + 3 pre-explode) and audio

var bomb_id: String = ""
var bomb_timer: float = 3.0

# Animation state
var animated_sprite: AnimatedSprite2D
var audio_player: AudioStreamPlayer2D
var timer_label: Label

# Asset paths (loaded at runtime)
const SOUND_PLANT_PATH = "res://res/sounds/bombs/bomb_plant.ogg"
const SOUND_EXPLOSION_PATH = "res://res/sounds/bombs/bomb_explosion.ogg"

const BOMB_SPRITE_PATHS = {
	"idle": [
		"res://res/bombs/sbomberman/bomb-01.png",
		"res://res/bombs/sbomberman/bomb-02.png",
		"res://res/bombs/sbomberman/bomb-03.png"
	],
	"explode": [
		"res://res/bombs/sbomberman/explode-01.png",
		"res://res/bombs/sbomberman/explode-02.png",
		"res://res/bombs/sbomberman/explode-03.png"
	]
}

var is_planted := false
var pre_explode_threshold = 0.5  # Start pre-explode animation at 0.5s remaining

func _ready():
	# Create animated sprite
	animated_sprite = AnimatedSprite2D.new()
	animated_sprite.sprite_frames = create_sprite_frames()
	add_child(animated_sprite)
	
	# Create audio player
	audio_player = AudioStreamPlayer2D.new()
	add_child(audio_player)
	
	# Create timer label for debugging
	timer_label = Label.new()
	timer_label.position = Vector2(-15, -35)
	timer_label.add_theme_font_size_override("font_size", 20)
	add_child(timer_label)
	
	# Play idle animation if frames loaded successfully
	if animated_sprite.sprite_frames.has_animation("idle"):
		animated_sprite.play("idle")
	else:
		# Fallback: create a simple colored rect if sprites failed to load
		var fallback = ColorRect.new()
		fallback.size = Vector2(24, 24)
		fallback.position = Vector2(-12, -12)
		fallback.color = Color(0.1, 0.1, 0.1)
		add_child(fallback)
	animated_sprite.play("idle")

func create_sprite_frames() -> SpriteFrames:
	var frames = SpriteFrames.new()
	
	# Idle animation (3 frames, looping)
	frames.add_animation("idle")
	frames.set_animation_loop("idle", true)
	frames.set_animation_speed("idle", 3.0)  # 3 FPS
	for path in BOMB_SPRITE_PATHS["idle"]:
		var texture = load_texture_from_png(path)
		if texture:
			frames.add_frame("idle", texture)
	
	# Pre-explode animation (3 frames, looping fast)
	frames.add_animation("explode")
	frames.set_animation_loop("explode", true)
	frames.set_animation_speed("explode", 12.0)  # 12 FPS, faster blink
	for path in BOMB_SPRITE_PATHS["explode"]:
		var texture = load_texture_from_png(path)
		if texture:
			frames.add_frame("explode", texture)
	
	return frames

func load_texture_from_png(path: String) -> ImageTexture:
	"""Load a PNG file as an ImageTexture at runtime"""
	var image = Image.new()
	var err = image.load(path)
	if err != OK:
		print("[BombRenderer] Failed to load image: ", path, " Error: ", err)
		return null
	
	var texture = ImageTexture.create_from_image(image)
	return texture

func plant_bomb():
	"""Called when bomb is first placed - play plant sound"""
	if not is_planted:
		is_planted = true
		var sound = load_audio_from_ogg(SOUND_PLANT_PATH)
		if sound:
			audio_player.stream = sound
			audio_player.play()

func update_timer(timer: float):
	"""Update bomb timer and animation state"""
	bomb_timer = timer
	timer_label.text = "%.1f" % bomb_timer
	
	# Switch to pre-explode animation when timer is low
	if bomb_timer <= pre_explode_threshold and animated_sprite.animation != "explode":
		animated_sprite.play("explode")

func explode():
	"""Called when bomb explodes - play explosion sound"""
	var sound = load_audio_from_ogg(SOUND_EXPLOSION_PATH)
	if sound:
		audio_player.stream = sound
		audio_player.play()
	# Visual will be removed by game_view when state updates

func load_audio_from_ogg(path: String) -> AudioStream:
	"""Load an OGG file as an AudioStream at runtime"""
	# TODO: OGG files require .import files in Godot 4
	# For now, skip audio until we can generate .import files or use a different format
	return null
