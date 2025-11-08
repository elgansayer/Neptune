extends Node2D
class_name ExplosionSegment

## Visual segment for a single explosion tile. Handles texture lookup
## based on direction, end-caps, and progressive size stages.

const EXPLOSION_BASE_PATH := "res://res/explosion/sbomberman/"
const SIZE_STAGE_SUFFIX := {
	"big": "01",
	"medium": "02",
	"small": "03",
	"smaller": "04"
}
const SPRITE_MAP := {
	"middle": "middle",
	"h_middle": "horizontal",
	"v_middle": "verticle",
	"h_end": "horizontal",
	"v_end": "verticle",
	"left": "left",
	"right": "right",
	"up": "up",
	"down": "down"
}

static var _texture_cache := {}

@onready var sprite: Sprite2D = $Sprite

var _direction: String = "middle"
var _is_end := false
var _sprite_type := "middle"
var _current_stage := "big"

func configure(direction: String, is_end: bool, size_stage: String):
	_direction = direction
	_is_end = is_end
	_sprite_type = _resolve_sprite_type(direction, is_end)
	_current_stage = size_stage
	_update_orientation()
	_update_texture()

func update_size_stage(size_stage: String):
	if _current_stage == size_stage:
		return
	_current_stage = size_stage
	_update_texture()

func _resolve_sprite_type(direction: String, is_end: bool) -> String:
	if direction == "middle":
		return "middle"
	elif direction in ["left", "right"]:
		return "h_end" if is_end else "h_middle"
	elif direction in ["up", "down"]:
		return "v_end" if is_end else "v_middle"
	return "middle"

func _update_orientation():
	if not sprite:
		return
	sprite.flip_h = false
	sprite.flip_v = false
	if _direction == "right":
		sprite.flip_h = true
	elif _direction == "down":
		sprite.flip_v = true

func _update_texture():
	if not sprite:
		return
	var base_name = SPRITE_MAP.get(_sprite_type, "middle")
	var texture = _get_texture(base_name, _current_stage)
	if texture:
		sprite.texture = texture

func _get_texture(base_name: String, size_stage: String) -> Texture2D:
	var suffix = SIZE_STAGE_SUFFIX.get(size_stage, "01")
	var key = "%s:%s:%s" % [size_stage, base_name, suffix]
	if _texture_cache.has(key):
		return _texture_cache[key]
	var path = "%s%s/%s-%s.png" % [EXPLOSION_BASE_PATH, size_stage, base_name, suffix]
	var texture = load(path)
	if texture:
		_texture_cache[key] = texture
	return texture
