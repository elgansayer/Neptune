extends Node2D
class_name PowerUpRenderer

## Client-side powerup visual with animations from SBomberman
## Handles spawn/idle/pickup/explode animations with shadows

var powerup_id: String = ""
var powerup_type: int = 0  # ServerPowerUp.PowerUpType enum value

# Animation nodes
var animated_sprite: AnimatedSprite2D
var shadow_sprite: Sprite2D
var audio_player: AudioStreamPlayer2D

# Asset paths (loaded at runtime)
const SOUND_PATHS = {
	"pickup": "res://res/sounds/items/pickup.ogg",
	"pickup_special": "res://res/sounds/items/pickup_special.ogg",
	"pickup_glove": "res://res/sounds/items/pickup_powerglove.ogg",
	"pickup_egg": "res://res/sounds/items/pickup_egg.ogg",
	"virus": "res://res/sounds/items/got_virus.ogg"
}

const SHADOW_PATH = "res://res/items/sbomberman/shadow.png"

# Powerup sprite paths (6 frames per type)
const SPRITE_PATHS = {
	"bomb": [
		"res://res/items/sbomberman/itm-bomb-01.png",
		"res://res/items/sbomberman/itm-bomb-02.png",
		"res://res/items/sbomberman/itm-bomb-03.png",
		"res://res/items/sbomberman/itm-bomb-04.png",
		"res://res/items/sbomberman/itm-bomb-05.png",
		"res://res/items/sbomberman/itm-bomb-06.png",
	],
	"fire": [
		"res://res/items/sbomberman/itm-fire-01.png",
		"res://res/items/sbomberman/itm-fire-02.png",
		"res://res/items/sbomberman/itm-fire-03.png",
		"res://res/items/sbomberman/itm-fire-04.png",
		"res://res/items/sbomberman/itm-fire-05.png",
		"res://res/items/sbomberman/itm-fire-06.png",
	],
	"skate": [
		"res://res/items/sbomberman/itm-skate-01.png",
		"res://res/items/sbomberman/itm-skate-02.png",
		"res://res/items/sbomberman/itm-skate-03.png",
		"res://res/items/sbomberman/itm-skate-04.png",
		"res://res/items/sbomberman/itm-skate-05.png",
		"res://res/items/sbomberman/itm-skate-06.png",
	],
	"kickbomb": [
		"res://res/items/sbomberman/itm-kickbomb-01.png",
		"res://res/items/sbomberman/itm-kickbomb-02.png",
		"res://res/items/sbomberman/itm-kickbomb-03.png",
		"res://res/items/sbomberman/itm-kickbomb-04.png",
		"res://res/items/sbomberman/itm-kickbomb-05.png",
		"res://res/items/sbomberman/itm-kickbomb-06.png",
	],
	"pglove": [
		"res://res/items/sbomberman/itm-pglove-01.png",
		"res://res/items/sbomberman/itm-pglove-02.png",
		"res://res/items/sbomberman/itm-pglove-03.png",
		"res://res/items/sbomberman/itm-pglove-04.png",
		"res://res/items/sbomberman/itm-pglove-05.png",
		"res://res/items/sbomberman/itm-pglove-06.png",
	],
	"skull": [
		"res://res/items/sbomberman/itm-skull-01.png",
		"res://res/items/sbomberman/itm-skull-02.png",
		"res://res/items/sbomberman/itm-skull-03.png",
		"res://res/items/sbomberman/itm-skull-04.png",
		"res://res/items/sbomberman/itm-skull-05.png",
		"res://res/items/sbomberman/itm-skull-06.png",
	],
}

# Smoke explosion sprite paths
const SMOKE_PATHS = [
	"res://res/items/sbomberman/itemsmoke-01.png",
	"res://res/items/sbomberman/itemsmoke-02.png",
	"res://res/items/sbomberman/itemsmoke-03.png",
	"res://res/items/sbomberman/itemsmoke-04.png",
	"res://res/items/sbomberman/itemsmoke-05.png",
]

var spawn_timer: Timer
var is_spawned := false

func _ready():
	# Create shadow sprite (under powerup)
	shadow_sprite = Sprite2D.new()
	var shadow_tex = load_texture_from_png(SHADOW_PATH)
	if shadow_tex:
		shadow_sprite.texture = shadow_tex
	shadow_sprite.z_index = -1
	shadow_sprite.position = Vector2(0, 4)  # Slightly below center
	add_child(shadow_sprite)
	
	# Create animated sprite
	animated_sprite = AnimatedSprite2D.new()
	animated_sprite.sprite_frames = create_sprite_frames()
	add_child(animated_sprite)
	
	# Create audio player
	audio_player = AudioStreamPlayer2D.new()
	add_child(audio_player)
	
	# Create spawn timer (for spin animation after 5 seconds)
	spawn_timer = Timer.new()
	spawn_timer.wait_time = 5.0
	spawn_timer.one_shot = true
	spawn_timer.timeout.connect(_on_spawn_timer_timeout)
	add_child(spawn_timer)
	
	# Play spawn animation
	play_spawn_animation()

func create_sprite_frames() -> SpriteFrames:
	var frames = SpriteFrames.new()
	
	# Create animations for each powerup type
	for type_name in SPRITE_PATHS:
		frames.add_animation(type_name)
		frames.set_animation_loop(type_name, true)
		frames.set_animation_speed(type_name, 8.0)  # 8 FPS
		for sprite_path in SPRITE_PATHS[type_name]:
			var texture = load_texture_from_png(sprite_path)
			if texture:
				frames.add_frame(type_name, texture)
	
	# Create smoke explosion animation
	frames.add_animation("explode")
	frames.set_animation_loop("explode", false)
	frames.set_animation_speed("explode", 10.0)
	for sprite_path in SMOKE_PATHS:
		var texture = load_texture_from_png(sprite_path)
		if texture:
			frames.add_frame("explode", texture)
	
	return frames

func load_texture_from_png(path: String) -> ImageTexture:
	"""Load a PNG file as an ImageTexture at runtime"""
	var image = Image.new()
	var err = image.load(path)
	if err != OK:
		return null
	
	var texture = ImageTexture.create_from_image(image)
	return texture

func set_powerup_type(type_value: int):
	"""Set the powerup type and play appropriate animation"""
	powerup_type = type_value
	
	var animation_name = get_animation_name_for_type(type_value)
	if animated_sprite.sprite_frames.has_animation(animation_name):
		animated_sprite.play(animation_name)

func get_animation_name_for_type(type_value: int) -> String:
	"""Map powerup type enum to animation name"""
	match type_value:
		0:  # BOMB_INCREASE
			return "bomb"
		1:  # RANGE_INCREASE
			return "fire"
		2:  # SPEED_INCREASE
			return "skate"
		3:  # BOMB_KICKER
			return "kickbomb"
		4:  # POWER_GLOVE
			return "pglove"
		5:  # VIRUS
			return "skull"
		_:
			return "bomb"

func play_spawn_animation():
	"""Play spawn animation (bounce up from block)"""
	# Simple bounce-in with tween
	var tween = create_tween()
	tween.set_ease(Tween.EASE_OUT)
	tween.set_trans(Tween.TRANS_BOUNCE)
	
	# Start below and bounce up
	position.y += 20
	tween.tween_property(self, "position:y", position.y - 20, 0.5)
	
	# Start timer for spin animation
	spawn_timer.start()
	is_spawned = true

func _on_spawn_timer_timeout():
	"""After 5 seconds, start spin animation"""
	# Add rotation tween for "spin" effect
	var tween = create_tween()
	tween.set_loops()
	tween.tween_property(animated_sprite, "rotation", TAU, 2.0)

func play_pickup_animation():
	"""Play pickup animation and sound"""
	spawn_timer.stop()
	
	# Play pickup sound based on type
	var sound_key = "pickup"
	match powerup_type:
		4:  # POWER_GLOVE
			sound_key = "pickup_glove"
		5:  # VIRUS
			sound_key = "virus"
	
	var sound = load_audio_from_ogg(SOUND_PATHS[sound_key])
	if sound:
		audio_player.stream = sound
		audio_player.play()
	
	# Fade out animation
	var tween = create_tween()
	tween.set_parallel(true)
	tween.tween_property(self, "modulate:a", 0.0, 0.3)
	tween.tween_property(self, "position:y", position.y - 30, 0.3)
	tween.finished.connect(queue_free)

func play_explode_animation():
	"""Play explosion smoke animation"""
	spawn_timer.stop()
	shadow_sprite.visible = false
	
	# Play smoke animation
	animated_sprite.play("explode")
	animated_sprite.animation_finished.connect(queue_free)

func load_audio_from_ogg(path: String) -> AudioStream:
	"""Load an OGG file as an AudioStream at runtime"""
	# TODO: OGG files require .import files in Godot 4
	# For now, skip audio until we can generate .import files or use a different format
	return null
