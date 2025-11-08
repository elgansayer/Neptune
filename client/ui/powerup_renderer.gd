extends Node2D
class_name PowerUpRenderer

## Client-side powerup visual with animations from SBomberman
## Handles spawn/idle/pickup/explode animations with shadows

var powerup_id: String = ""
var powerup_type: int = 0  # ServerPowerUp.PowerUpType enum value

const SOUND_MAP = {
	"pickup": preload("res://res/sounds/items/pickup.ogg"),
	"pickup_special": preload("res://res/sounds/items/pickup_special.ogg"),
	"pickup_glove": preload("res://res/sounds/items/pickup_powerglove.ogg"),
	"pickup_egg": preload("res://res/sounds/items/pickup_egg.ogg"),
	"virus": preload("res://res/sounds/items/got_virus.ogg")
}

@onready var shadow_sprite: Sprite2D = $Shadow
@onready var item_sprite: AnimatedSprite2D = $ItemSprite
@onready var audio_player: AudioStreamPlayer2D = $AudioStreamPlayer2D
@onready var spawn_timer: Timer = $SpinTimer

var is_spawned := false

func _ready():
	var timeout_callable := Callable(self, "_on_spawn_timer_timeout")
	if spawn_timer and not spawn_timer.timeout.is_connected(timeout_callable):
		spawn_timer.timeout.connect(timeout_callable)
	item_sprite.rotation = 0.0
	item_sprite.play(get_animation_name_for_type(powerup_type))
	play_spawn_animation()

func set_powerup_type(type_value: int):
	"""Set the powerup type and play appropriate animation"""
	powerup_type = type_value
	
	var animation_name = get_animation_name_for_type(type_value)
	if item_sprite.sprite_frames.has_animation(animation_name):
		item_sprite.play(animation_name)

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
	tween.tween_property(item_sprite, "rotation", TAU, 2.0)

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
	
	var sound = SOUND_MAP.get(sound_key, null)
	if sound:
		audio_player.stop()
		audio_player.stream = sound
		audio_player.play()
	
	# Fade out animation
	var tween = create_tween()
	tween.set_parallel(true)
	tween.tween_property(self, "modulate:a", 0.0, 0.3)
	tween.tween_property(self, "position:y", position.y - 30, 0.3)
	tween.finished.connect(Callable(self, "queue_free"))

func play_explode_animation():
	"""Play explosion smoke animation"""
	spawn_timer.stop()
	shadow_sprite.visible = false
	
	# Play smoke animation
	item_sprite.play("explode")
	var free_callable := Callable(self, "queue_free")
	if not item_sprite.animation_finished.is_connected(free_callable):
		item_sprite.animation_finished.connect(free_callable, Object.CONNECT_ONE_SHOT)
