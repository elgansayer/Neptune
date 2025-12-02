extends Node2D
class_name PowerUpRenderer

## Client-side powerup visual with animations from SBomberman
## Handles spawn/idle/pickup/explode animations with shadows
## Scale is calculated dynamically based on GameConfig.TILE_SIZE

var powerup_id: String = ""
var powerup_type: int = 0  # ServerPowerUp.PowerUpType enum value

# Sprite base size (Saturn Bomberman native)
const SPRITE_SIZE: float = 16.0
# Shadow base size
const SHADOW_WIDTH: float = 40.0
const SHADOW_HEIGHT: float = 20.0

# Calculated scale values (set in _ready based on tile size)
var item_scale: float = 1.0
var shadow_scale: float = 1.0

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
	# Calculate scale based on tile size from map
	# Items should be about 75% of tile size
	var tile_size: float = GameConfig.TILE_SIZE
	item_scale = (tile_size * 0.75) / SPRITE_SIZE
	# Shadow should be about 90% of tile width
	shadow_scale = (tile_size * 0.9) / SHADOW_WIDTH
	
	# Apply scales
	item_sprite.scale = Vector2(item_scale, item_scale)
	shadow_sprite.scale = Vector2(shadow_scale, shadow_scale)
	
	# Position shadow at bottom of tile, item floats above
	shadow_sprite.position = Vector2(0, tile_size * 0.3)
	item_sprite.position = Vector2(0, -tile_size * 0.1)
	
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
	
	# Start below and bounce up - scale with tile size
	var bounce_distance = GameConfig.TILE_SIZE * 0.3
	position.y += bounce_distance
	tween.tween_property(self, "position:y", position.y - bounce_distance, 0.5)
	
	# Start timer for spin animation
	spawn_timer.start()
	is_spawned = true

func _on_spawn_timer_timeout():
	"""After 5 seconds, start Y-axis spin animation (scale flip effect)"""
	_start_y_spin()

func _start_y_spin():
	"""Create a Y-axis rotation effect using scale.x oscillation"""
	var tween = create_tween()
	tween.set_loops()
	# Scale X from item_scale -> 0 -> -item_scale -> 0 -> item_scale to simulate Y-axis rotation
	tween.tween_property(item_sprite, "scale:x", 0.0, 0.15).set_ease(Tween.EASE_IN)
	tween.tween_property(item_sprite, "scale:x", -item_scale, 0.15).set_ease(Tween.EASE_OUT)
	tween.tween_property(item_sprite, "scale:x", 0.0, 0.15).set_ease(Tween.EASE_IN)
	tween.tween_property(item_sprite, "scale:x", item_scale, 0.15).set_ease(Tween.EASE_OUT)

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
	var float_distance = GameConfig.TILE_SIZE * 0.4
	tween.tween_property(self, "position:y", position.y - float_distance, 0.3)
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
