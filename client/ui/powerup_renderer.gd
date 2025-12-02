extends Node2D
class_name PowerUpRenderer

## Client-side powerup visual with animations from Saturn Bomberman
## Implements authentic "Hudson Bob" idle animation and spawn/pickup/explode effects
## 
## Saturn Bomberman Pickup Mechanics (from hardware analysis):
## - Idle Animation: 32-frame bobbing loop (0.53s at 60fps)
## - Y-Offset Pattern: 0 -> -1 -> -2 -> -3 (peak) -> -2 -> -1 -> 0 (integer steps)
## - Visual Offset: Items render at (TileCenterX, TileCenterY - 4) to "sit" on floor
## - Collection Window: 6 pixels from tile center (Manhattan distance)
## - Spawn Delay: ~30 frames after soft block break before interactable

var powerup_id: String = ""
var powerup_type: int = 0  # ServerPowerUp.PowerUpType enum value

# Sprite base size (Saturn Bomberman native: 16x16)
const SPRITE_SIZE: float = 16.0
const SHADOW_WIDTH: float = 40.0

# Saturn Bomberman "Hudson Bob" animation table
# 32 frames total, 4 frames per step, Y-offsets in pixels (at 16px tile size)
const SATURN_BOB_OFFSETS: Array[int] = [
	0, 0, 0, 0,      # Frames 00-03: Lowest
	-1, -1, -1, -1,  # Frames 04-07: Rising
	-2, -2, -2, -2,  # Frames 08-11: Rising
	-3, -3, -3, -3,  # Frames 12-15: Peak
	-3, -3, -3, -3,  # Frames 16-19: Peak (Hold)
	-2, -2, -2, -2,  # Frames 20-23: Falling
	-1, -1, -1, -1,  # Frames 24-27: Falling
	0, 0, 0, 0       # Frames 28-31: Land
]

# Animation state
var bob_frame: int = 0
var bob_active: bool = false
var base_y_position: float = 0.0
var spawn_complete: bool = false

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

func _ready():
	# Calculate scale based on tile size from map
	var tile_size: float = GameConfig.TILE_SIZE
	pixel_scale = tile_size / 16.0  # Saturn native is 16px tiles
	
	# Items are 16x16 sprites, scale to match tile size (1:1 with tile)
	item_scale = pixel_scale
	
	# Shadow is large oval spanning most of the tile width
	# Original shadow is 40x20, we want it to be ~80% of tile width
	# So target width = tile_size * 0.8, scale = (tile_size * 0.8) / 40
	shadow_scale = (tile_size * 0.8) / SHADOW_WIDTH
	
	# Apply scales
	item_sprite.scale = Vector2(item_scale, item_scale)
	shadow_sprite.scale = Vector2(shadow_scale, shadow_scale)
	
	# Shadow sits at the bottom of the tile (near floor level)
	# Looking at reference: shadow is at about 70-80% down from tile center
	shadow_sprite.position = Vector2(0, tile_size * 0.35)
	
	# Item floats ABOVE the tile - its bottom edge at roughly tile center
	# This means the item center is at -0.5 * item_height above tile center
	# Item is tile_size tall, so center is at -tile_size * 0.5
	base_y_position = -tile_size * 0.5
	item_sprite.position = Vector2(0, base_y_position)
	
	item_sprite.rotation = 0.0
	item_sprite.play(get_animation_name_for_type(powerup_type))
	
	# Start spawn animation
	play_spawn_animation()

func _physics_process(_delta: float):
	if not bob_active or not spawn_complete:
		return
	
	# Advance bob animation frame (runs at physics rate, ~60fps)
	bob_frame = (bob_frame + 1) % SATURN_BOB_OFFSETS.size()
	
	# Apply integer-stepped Y offset (scaled to current tile size)
	var bob_offset = SATURN_BOB_OFFSETS[bob_frame] * pixel_scale
	item_sprite.position.y = base_y_position + bob_offset

func set_powerup_type(type_value: int):
	"""Set the powerup type and play appropriate animation"""
	powerup_type = type_value
	
	if item_sprite and item_sprite.sprite_frames:
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
	"""
	Saturn Bomberman spawn sequence:
	- Frames 0-30: Soft block dissolves (handled elsewhere)
	- Frame 31: Pickup instantiated
	- Frames 31-45: Flash animation (white -> normal palette) ~15 frames
	- Frame 46+: Idle state
	"""
	spawn_complete = false
	bob_active = false
	
	var tile_size = GameConfig.TILE_SIZE
	
	# Start with flash effect
	modulate.a = 1.0
	shadow_sprite.scale = Vector2(shadow_scale, shadow_scale)
	item_sprite.position.y = base_y_position
	item_sprite.modulate = Color(2.0, 2.0, 2.0, 1.0)  # White flash
	
	var tween = create_tween()
	
	# Flash fades to normal over ~15 frames (0.25s)
	tween.tween_property(item_sprite, "modulate", Color.WHITE, 0.25)
	
	# When spawn complete, item is ready
	tween.tween_callback(_on_spawn_complete)

func _on_spawn_complete():
	"""Called when spawn animation finishes - start idle bob"""
	spawn_complete = true
	# Disable bob animation - items stay static after spawn
	# Set bob_active = true to enable the Saturn "Hudson Bob" idle animation
	bob_active = false
	bob_frame = 0
	# Ensure item is at base position
	item_sprite.position.y = base_y_position

func play_pickup_animation():
	"""
	Saturn Bomberman collection:
	- Item sprite vanishes on next frame
	- Floating text/icon indicator appears above player
	- Sound: high-pitched chime (2khz, 100ms decay)
	"""
	bob_active = false
	
	# Play pickup sound based on type
	# Saturn: Fire/Bomb/Skate = "Chime A", Kick/Glove = "Chime B" (deeper), Skull = "Buzz"
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
	
	# Saturn: instant vanish with upward float indicator
	var tween = create_tween()
	tween.set_parallel(true)
	
	# Quick flash then vanish
	tween.tween_property(item_sprite, "modulate", Color(3.0, 3.0, 3.0, 1.0), 0.05)
	tween.chain().tween_property(self, "modulate:a", 0.0, 0.1)
	
	# Float upward
	var float_distance = GameConfig.TILE_SIZE * 0.5
	tween.tween_property(item_sprite, "position:y", item_sprite.position.y - float_distance, 0.2).set_ease(Tween.EASE_OUT)
	
	# Shadow shrinks
	tween.tween_property(shadow_sprite, "scale", Vector2.ZERO, 0.1)
	
	tween.finished.connect(queue_free)

func play_explode_animation():
	"""
	Saturn Bomberman explosion interaction:
	- Item transitions to "Burning Debris" state
	- Generic burning rubbish animation (4 frames, loops 3x)
	- Item removed, does NOT respawn
	- ~0.5s burn duration
	"""
	bob_active = false
	shadow_sprite.visible = false
	
	# Play smoke/burn animation
	if item_sprite.sprite_frames.has_animation("explode"):
		item_sprite.play("explode")
		var free_callable := Callable(self, "queue_free")
		if not item_sprite.animation_finished.is_connected(free_callable):
			item_sprite.animation_finished.connect(free_callable, Object.CONNECT_ONE_SHOT)
	else:
		# Fallback: quick burn effect
		var tween = create_tween()
		tween.tween_property(item_sprite, "modulate", Color(1.5, 0.5, 0.0, 1.0), 0.1)
		tween.tween_property(item_sprite, "modulate", Color(0.3, 0.3, 0.3, 0.5), 0.3)
		tween.tween_property(self, "modulate:a", 0.0, 0.2)
		tween.tween_callback(queue_free)
