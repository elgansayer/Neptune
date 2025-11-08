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

var is_planted := false
var warning_started := false
var pre_explode_threshold := 0.5  # Begin warning animation when timer is low

func _ready():
	if animated_sprite:
		animated_sprite.play("idle")
	if timer_label:
		timer_label.text = ""

func plant_bomb():
	"""Play the plant sound the first time the bomb appears."""
	if is_planted:
		return
	is_planted = true
	if audio_player and SOUND_PLANT:
		audio_player.stream = SOUND_PLANT
		audio_player.play()

func update_timer(timer: float):
	"""Update countdown visuals and trigger warning animation when appropriate."""
	bomb_timer = timer
	if timer_label:
		timer_label.text = "%.1f" % bomb_timer
	if bomb_timer <= pre_explode_threshold and not warning_started:
		warning_started = true
		if animated_sprite:
			animated_sprite.play("warning")

func explode():
	"""Play explosion audio and hide the sprite until the node is removed."""
	if audio_player and SOUND_EXPLOSION:
		audio_player.stream = SOUND_EXPLOSION
		audio_player.play()
	if animated_sprite:
		animated_sprite.visible = false
