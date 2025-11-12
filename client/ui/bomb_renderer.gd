extends Node2D
class_name BombRenderer

## Client-side bomb visual backed by a dedicated scene.
## Preloads textures, audio, and animations so gameplay code stays lightweight.

const SOUND_PLANT: AudioStream = preload("res://res/sounds/bombs/bomb_plant.ogg")
const SOUND_EXPLOSION: AudioStream = preload("res://res/sounds/bombs/bomb_explosion.ogg")

@onready var animated_sprite: AnimatedSprite2D = $AnimatedSprite2D
@onready var audio_player: AudioStreamPlayer2D = $AudioStreamPlayer2D
@onready var timer_label: Label = $TimerLabel

var bomb_id: String = ""
var bomb_timer: float = 3.0
var is_kicked := false

var is_planted := false
var has_exploded := false

func _ready():
	if animated_sprite:
		animated_sprite.play("idle")
		animated_sprite.speed_scale = 1.0
		if animated_sprite.sprite_frames.has_animation("explode"):
			animated_sprite.sprite_frames.set_animation_loop("explode", false)
		animated_sprite.animation_finished.connect(_on_animation_finished, Object.CONNECT_ONE_SHOT)
	if timer_label:
		timer_label.text = ""

func plant_bomb():
	"""Play the plant sound the first time the bomb appears."""
	if is_planted:
		return
	is_planted = true
	has_exploded = false
	if animated_sprite:
		animated_sprite.visible = true
		animated_sprite.play("idle")
		animated_sprite.speed_scale = 1.0
	if timer_label:
		timer_label.visible = false
		timer_label.text = ""
	if audio_player and SOUND_PLANT:
		audio_player.stream = SOUND_PLANT
		audio_player.play()

func update_timer(timer: float):
	"""Update countdown visuals and trigger warning animation when appropriate."""
	if has_exploded:
		return
	bomb_timer = timer
	if timer_label:
		timer_label.text = "%.1f" % bomb_timer

func set_kicked_state(kicked: bool):
	"""Update visual feedback for kicked bombs"""
	is_kicked = kicked
	if animated_sprite and is_kicked:
		# Make the bomb visually distinct when kicked (faster animation, different color modulation)
		animated_sprite.speed_scale = 2.0
		animated_sprite.modulate = Color(1.0, 0.8, 0.8, 1.0)  # Slight red tint
	elif animated_sprite:
		animated_sprite.speed_scale = 1.0
		animated_sprite.modulate = Color(1.0, 1.0, 1.0, 1.0)  # Normal color

func explode():
	"""Play explosion audio and hide the sprite until the node is removed."""
	if has_exploded:
		return
	has_exploded = true
	if timer_label:
		timer_label.visible = false
		timer_label.text = ""
	if audio_player and SOUND_EXPLOSION:
		audio_player.stream = SOUND_EXPLOSION
		audio_player.play()
	if animated_sprite:
		animated_sprite.visible = true
		animated_sprite.speed_scale = 1.0
		animated_sprite.play("explode")

func _on_animation_finished(anim_name: StringName = &""):
	if anim_name == "explode" and has_exploded and animated_sprite:
		animated_sprite.visible = false
