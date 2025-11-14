extends Node2D
class_name BombRenderer

## Client-side bomb visual backed by a dedicated scene.
## Preloads textures, audio, and animations so gameplay code stays lightweight.
## Supports Power Glove states: PLANTED, CARRIED, THROWN, LANDED

const SOUND_PLANT: AudioStream = preload("res://res/sounds/bombs/bomb_plant.ogg")
const SOUND_EXPLOSION: AudioStream = preload("res://res/sounds/bombs/bomb_explosion.ogg")

@onready var animated_sprite: AnimatedSprite2D = $AnimatedSprite2D
@onready var audio_player: AudioStreamPlayer2D = $AudioStreamPlayer2D
@onready var timer_label: Label = $TimerLabel

var bomb_id: String = ""
var bomb_timer: float = 3.0

var is_planted := false
var has_exploded := false

# Power Glove state
enum BombState { PLANTED, CARRIED, THROWN, LANDED }
var bomb_state: BombState = BombState.PLANTED
var z_offset: float = 0.0  # Visual Z height for thrown bombs

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

# ============ POWER GLOVE SUPPORT ============

func set_bomb_state(new_state: BombState):
	"""Update visual state for Power Glove system"""
	bomb_state = new_state
	
	match new_state:
		BombState.PLANTED:
			_show_planted_visual()
		BombState.CARRIED:
			_show_carried_visual()
		BombState.THROWN:
			_show_thrown_visual()
		BombState.LANDED:
			_show_planted_visual()  # Same as planted

func _show_planted_visual():
	"""Show normal planted bomb visual"""
	if animated_sprite:
		animated_sprite.visible = true
		animated_sprite.modulate = Color.WHITE
		animated_sprite.scale = Vector2.ONE

func _show_carried_visual():
	"""Visual feedback for carried bomb (slightly smaller, above player)"""
	if animated_sprite:
		animated_sprite.visible = true
		animated_sprite.modulate = Color(1.0, 1.0, 1.0, 0.9)  # Slightly transparent
		animated_sprite.scale = Vector2(0.8, 0.8)  # Slightly smaller

func _show_thrown_visual():
	"""Visual feedback for thrown bomb (uses z_offset for height)"""
	if animated_sprite:
		animated_sprite.visible = true
		animated_sprite.modulate = Color.WHITE
		animated_sprite.scale = Vector2.ONE

func update_z_height(z_height: float):
	"""Update visual position based on pseudo-3D height"""
	print("[BombRenderer] update_z_height called with z_height=", z_height)
	z_offset = z_height
	
	# Offset sprite upward to simulate height
	if animated_sprite:
		animated_sprite.position = Vector2(0, -z_offset)
		print("[BombRenderer] Set sprite position to: ", animated_sprite.position)
		
		# Scale slightly larger when higher (perspective effect)
		var scale_factor = 1.0 + (z_height / 200.0)  # Subtle scaling
		animated_sprite.scale = Vector2(scale_factor, scale_factor)
	
	# Shadow grows fainter when bomb is higher
	if timer_label:
		var shadow_alpha = 1.0 - (z_height / 150.0)
		timer_label.modulate = Color(1, 1, 1, clampf(shadow_alpha, 0.3, 1.0))

# ============ END POWER GLOVE SUPPORT ============
