extends Node2D
class_name PowerUpRenderer

## Client-side powerup visual with editable animations via AnimationPlayer
##
## Animations (edit in Godot Editor):
## - "spawn": Pop-in with bounce, flash, and scale overshoot
## - "idle": Static resting state after spawn
## - "pickup": Float up and fade out when collected
## - "explode": Burn effect when destroyed by explosion
## - "RESET": Default state for editor preview

var powerup_id: String = ""
var powerup_type: int = 0  # ServerPowerUp.PowerUpType enum value

# Sprite base size (Saturn Bomberman native: 16x16)
const SPRITE_SIZE: float = 16.0
const SHADOW_WIDTH: float = 40.0

# Calculated scale values (set in _ready based on tile size)
var item_scale: float = 1.0
var shadow_scale: float = 1.0
var pixel_scale: float = 1.0  # How many display pixels per Saturn pixel

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
@onready var anim_player: AnimationPlayer = $AnimationPlayer

func _ready():
	# Calculate scale based on tile size from map
	var tile_size: float = GameConfig.TILE_SIZE
	pixel_scale = tile_size / 16.0  # Saturn native is 16px tiles
	
	# Items are 16x16 sprites, scale to match tile size (1:1 with tile)
	item_scale = pixel_scale
	
	# Shadow is 40x20, we want it to be ~50% of tile width for a small oval
	# For 16px tiles: 40 * 0.2 = 8px wide (50% of 16)
	# For 64px tiles: 40 * 0.8 = 32px wide (50% of 64)
	shadow_scale = (tile_size * 0.5) / SHADOW_WIDTH
	
	# Apply base scales - these are the "1.0" reference for animations
	# Animations use relative multipliers (0, 1, 1.1, etc.)
	item_sprite.scale = Vector2(item_scale, item_scale)
	shadow_sprite.scale = Vector2(shadow_scale, shadow_scale)
	
	# Position shadow at bottom of tile
	shadow_sprite.position = Vector2(0, tile_size * 0.35)
	
	# Item floats above the tile
	item_sprite.position = Vector2(0, -tile_size * 0.5)
	
	item_sprite.rotation = 0.0
	item_sprite.play(get_animation_name_for_type(powerup_type))
	
	# Don't use AnimationPlayer autoplay - we need to set scales first
	# Then play spawn with proper scaling
	if anim_player:
		# Stop any autoplay
		anim_player.stop()
		# Play spawn animation using tweens so we can use calculated scales
		_play_spawn_tween()

func set_powerup_type(type_value: int):
	"""Set the powerup type and play appropriate animation"""
	powerup_type = type_value
	
	if item_sprite and item_sprite.sprite_frames:
		var animation_name = get_animation_name_for_type(type_value)
		if item_sprite.sprite_frames.has_animation(animation_name):
			item_sprite.play(animation_name)

func get_animation_name_for_type(type_value: int) -> String:
	"""Map powerup type enum to animation name
	
	Enum values from ServerPowerUp.PowerUpType:
	0: BOMB_INCREASE, 1: RANGE_INCREASE, 2: SPEED_INCREASE,
	3: BOMB_KICKER, 4: POWER_GLOVE, 5: LINE_BOMB,
	6: FULL_FIRE, 7: HEART, 8: GETA,
	9: REMOTE_BOMB, 10: POWER_BOMB, 11: RUBBER_BOMB, 12: PIERCE_BOMB,
	13: SKULL (VIRUS)
	"""
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
		5:  # LINE_BOMB
			return "bomb"  # Fallback to bomb animation until we have line_bomb sprites
		6:  # FULL_FIRE
			return "fire"  # Fallback to fire animation until we have full_fire sprites
		7:  # HEART
			return "bomb"  # Fallback until we have heart sprites
		8:  # GETA
			return "skate" # Fallback until we have geta sprites (maybe recolor?)
		9:  # REMOTE_BOMB
			return "bomb"  # Fallback until we have remote_bomb sprites
		10: # POWER_BOMB
			return "bomb"  # Fallback until we have power_bomb sprites
		11: # RUBBER_BOMB
			return "bomb"  # Fallback until we have rubber_bomb sprites
		12: # PIERCE_BOMB
			return "bomb"  # Fallback until we have pierce_bomb sprites
		13: # SKULL (VIRUS)
			return "skull"
		_:
			return "bomb"

func play_spawn_animation():
	"""Play the spawn animation (can be edited in AnimationPlayer)"""
	if anim_player:
		anim_player.play("spawn")

func play_pickup_animation():
	"""Play pickup animation and sound, then queue_free"""
	# Play pickup sound based on type
	var sound_key = "pickup"
	match powerup_type:
		3:  # BOMB_KICKER
			sound_key = "pickup_special"
		4:  # POWER_GLOVE
			sound_key = "pickup_glove"
		5:  # VIRUS
			sound_key = "virus"
	
	var sound = SOUND_MAP.get(sound_key, null)
	if sound:
		audio_player.stop()
		audio_player.stream = sound
		audio_player.play()
	
	# Play the pickup animation
	if anim_player:
		anim_player.play("pickup")
	else:
		# Fallback if no AnimationPlayer
		queue_free()

func play_explode_animation():
	"""Play explosion/burn animation, then queue_free"""
	if anim_player:
		anim_player.play("explode")
	elif item_sprite.sprite_frames.has_animation("explode"):
		item_sprite.play("explode")
		item_sprite.animation_finished.connect(queue_free, CONNECT_ONE_SHOT)
	else:
		queue_free()

func _on_animation_finished(anim_name: StringName):
	"""Handle animation completion - connected in scene"""
	match anim_name:
		"spawn":
			# After spawn, stay idle (do nothing, just sit there)
			pass
		"pickup":
			queue_free()
		"explode":
			queue_free()

func _play_spawn_tween():
	"""Play spawn animation using tweens with proper calculated scales"""
	var tile_size = GameConfig.TILE_SIZE
	var base_y = -tile_size * 0.5
	
	# Start from zero/hidden
	item_sprite.scale = Vector2.ZERO
	shadow_sprite.scale = Vector2.ZERO
	item_sprite.position.y = base_y + tile_size * 0.3  # Start lower
	item_sprite.modulate = Color(2, 2, 2, 1)  # White flash
	
	var tween = create_tween()
	
	# Flash fades
	tween.tween_property(item_sprite, "modulate", Color.WHITE, 0.08)
	
	# Item pops in with overshoot
	tween.parallel().tween_property(item_sprite, "scale", Vector2(item_scale * 1.2, item_scale * 1.2), 0.15)\
		.set_ease(Tween.EASE_OUT)
	tween.tween_property(item_sprite, "scale", Vector2(item_scale, item_scale), 0.2)\
		.set_ease(Tween.EASE_IN_OUT)
	
	# Item bounces up then settles
	tween.parallel().tween_property(item_sprite, "position:y", base_y - tile_size * 0.15, 0.2)\
		.set_ease(Tween.EASE_OUT)
	tween.tween_property(item_sprite, "position:y", base_y, 0.15)\
		.set_trans(Tween.TRANS_BOUNCE).set_ease(Tween.EASE_OUT)
	
	# Shadow grows in (delayed)
	tween.parallel().tween_property(shadow_sprite, "scale", Vector2(shadow_scale * 1.1, shadow_scale * 1.1), 0.2)\
		.set_delay(0.1).set_ease(Tween.EASE_OUT)
	tween.tween_property(shadow_sprite, "scale", Vector2(shadow_scale, shadow_scale), 0.15)
