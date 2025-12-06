extends Node2D

signal action_started(action_name, action_type)
signal action_stopped(action_name, action_type)
signal action_info(info_dict)

enum GrowthLevel {
	BABY,
	TEEN,
	ADULT
}

@export var current_level: GrowthLevel = GrowthLevel.BABY:
	set(value):
		current_level = value
		_update_visibility()

@export_group("Rider Offsets")
@export var offset_baby: Vector2 = Vector2(0, -10)
@export var offset_teen: Vector2 = Vector2(0, -20)
@export var offset_adult: Vector2 = Vector2(0, -30)

## Dictionary mapping "animation_name:frame_index" keys to Vector2 offsets relative to base.
## Example: { "kick:1": Vector2(5, -2) }
@export var frame_offsets: Dictionary = {}

var _current_sprite: AnimatedSprite2D

func _ready() -> void:
	# Initialize visibility and sprite reference
	_update_visibility()
	
	# Connect animation finished signals for all sprites
	if has_node("baby"):
		$baby.animation_finished.connect(_on_animation_finished)
		$baby.frame_changed.connect(_on_frame_changed)
	if has_node("teen"):
		$teen.animation_finished.connect(_on_animation_finished)
		$teen.frame_changed.connect(_on_frame_changed)
	if has_node("adult"):
		$adult.animation_finished.connect(_on_animation_finished)
		$adult.frame_changed.connect(_on_frame_changed)

func set_growth_level(level: GrowthLevel) -> void:
	current_level = level

func _update_visibility() -> void:
	var baby = get_node_or_null("baby")
	var teen = get_node_or_null("teen")
	var adult = get_node_or_null("adult")
	
	if baby: baby.visible = (current_level == GrowthLevel.BABY)
	if teen: teen.visible = (current_level == GrowthLevel.TEEN)
	if adult: adult.visible = (current_level == GrowthLevel.ADULT)
	
	match current_level:
		GrowthLevel.BABY:
			_current_sprite = baby
		GrowthLevel.TEEN:
			_current_sprite = teen
		GrowthLevel.ADULT:
			_current_sprite = adult

func get_rider_offset() -> Vector2:
	match current_level:
		GrowthLevel.BABY:
			return offset_baby
		GrowthLevel.TEEN:
			return offset_teen
		GrowthLevel.ADULT:
			return offset_adult
	return Vector2.ZERO

func get_dynamic_offset() -> Vector2:
	var base = get_rider_offset()
	if not _current_sprite or not _current_sprite.sprite_frames:
		return base
		
	var anim_name = _current_sprite.animation
	var frame = _current_sprite.frame
	var key = "%s:%d" % [anim_name, frame]
	
	var anim_offset = frame_offsets.get(key, Vector2.ZERO)
	return base + anim_offset

func run_action(action_name: String) -> Dictionary:
	# Returning start info immediately
	var info = {
		"started": true,
		"action": action_name,
		"level": current_level,
		"type": "physical" # Default type, can be customized
	}
	
	if not _current_sprite:
		info["started"] = false
		return info
	
	# Map generic action names to specific animation names if needed
	# For now assuming action_name matches animation name suffixes or we construct it.
	# The user requested "kick". The sprite frames have "down_kick", "left_kick", etc.
	# We probably need a direction or use the current direction. 
	# For simplicity, we'll try to use the current direction of the sprite if it has one, 
	# or default to "down_kick" if we can't determine.
	# However, the user just said "run the action".
	# A robust way is to check the current animation prefix (e.g. "down_walk" -> "down_kick").
	
	var current_anim = _current_sprite.animation
	var direction = "down"
	if "left" in current_anim: direction = "left"
	elif "right" in current_anim: direction = "right"
	elif "up" in current_anim: direction = "up"
	
	var anim_to_play = direction + "_" + action_name
	
	# Fallback if direction-based animation doesn't exist, try naive name
	if not _current_sprite.sprite_frames.has_animation(anim_to_play):
		anim_to_play = action_name
		
	if _current_sprite.sprite_frames.has_animation(anim_to_play):
		_current_sprite.play(anim_to_play)
		action_started.emit(action_name, info["type"])
		return info
	else:
		push_warning("Animation not found: " + anim_to_play)
		info["started"] = false
		return info

func _on_animation_finished() -> void:
	# Assuming the last played action is what finished.
	# We can track the current action if needed.
	if _current_sprite:
		var params = _current_sprite.animation.split("_")
		if params.size() > 1:
			var action = params[1] # e.g. "kick" from "down_kick"
			action_stopped.emit(action, "physical")
		else:
			action_stopped.emit(_current_sprite.animation, "physical")

func _on_frame_changed() -> void:
	# Emit info update on frame change
	var off = get_dynamic_offset()
	action_info.emit({"offset": off, "frame": _current_sprite.frame})
