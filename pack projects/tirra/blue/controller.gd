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


## ============================================================================
## KILLED / EXPLODE SYSTEM
## Saturn Bomberman style death: play killed animation, sparkle particles,
## then rise out of screen while shrinking
## ============================================================================

signal killed_complete

var _is_dying := false

func killed() -> void:
	"""Called when Tirra is killed by an explosion.
	Plays killed animation, spawns particles, rises out of screen."""
	if _is_dying:
		return
	_is_dying = true
	
	# Stop any current action
	if _current_sprite:
		_current_sprite.stop()
	
	# Play killed animation
	if _current_sprite and _current_sprite.sprite_frames and _current_sprite.sprite_frames.has_animation("killed"):
		_current_sprite.play("killed")
	
	# Start sparkle particles if we have them
	var particles = get_node_or_null("Particles")
	if particles and particles is GPUParticles2D:
		particles.emitting = true
	
	# Wait for killed animation to finish (approx 1 second at 5fps with 4 frames)
	await get_tree().create_timer(0.8).timeout
	
	# Now rise out of screen while shrinking (SBomberman explode effect)
	_perform_death_rise()


func _perform_death_rise() -> void:
	"""Rise up and shrink to nothing, then remove self."""
	var tween = create_tween()
	tween.set_parallel(true)
	
	# Rise from current Y to Y-128 over 0.7 seconds
	tween.tween_property(self, "position:y", position.y - 128, 0.7)
	
	# Scale from 2x to 0 (start big, shrink to nothing)
	if _current_sprite:
		_current_sprite.scale = Vector2(2, 2)
		tween.tween_property(_current_sprite, "scale", Vector2.ZERO, 0.7)
	
	# Fade out slightly
	tween.tween_property(self, "modulate:a", 0.0, 0.7)
	
	await tween.finished
	
	killed_complete.emit()
	queue_free()


func explode() -> void:
	"""Alias for killed() - compatibility with SBomberman naming."""
	killed()


## ============================================================================
## GROWTH / LEVEL UP SYSTEM
## Tirra can grow from BABY -> TEEN -> ADULT by collecting more eggs
## ============================================================================

signal level_changed(new_level: GrowthLevel)

func level_up() -> void:
	"""Upgrade Tirra to the next growth level."""
	if current_level == GrowthLevel.BABY:
		set_growth_level(GrowthLevel.TEEN)
		_play_level_up_effect()
	elif current_level == GrowthLevel.TEEN:
		set_growth_level(GrowthLevel.ADULT)
		_play_level_up_effect()
	# Already adult, no more levels
	level_changed.emit(current_level)


func _play_level_up_effect() -> void:
	"""Visual effect when leveling up - flash and sparkle."""
	# Flash white briefly
	if _current_sprite:
		var original_modulate = _current_sprite.modulate
		_current_sprite.modulate = Color.WHITE * 2.0 # Bright flash
		await get_tree().create_timer(0.1).timeout
		_current_sprite.modulate = original_modulate
	
	# Emit particles if we have them
	var particles = get_node_or_null("Particles")
	if particles and particles is GPUParticles2D:
		particles.emitting = true


## ============================================================================
## HIGH KICK ACTION (Blue Tirra Special - Adult Only)
## Adult Blue Tirra performs a spinning kick that can launch bombs further
## The rider's direction changes during the spin animation
## ============================================================================

signal high_kick_started
signal high_kick_hit(bomb_node: Node) # Emitted when kick connects with a bomb
signal high_kick_complete

var _is_high_kicking := false
var _high_kick_distance := 4 # Base distance for adult high kick

func perform_high_kick(rider_direction: String) -> Dictionary:
	"""Perform the adult Blue Tirra's special high kick action.
	Only works at ADULT level. Returns info about the kick."""
	var info = {
		"started": false,
		"action": "high_kick",
		"level": current_level,
		"reason": ""
	}
	
	if current_level != GrowthLevel.ADULT:
		info["reason"] = "not_adult"
		return info
	
	if _is_high_kicking:
		info["reason"] = "already_kicking"
		return info
	
	if not _current_sprite:
		info["reason"] = "no_sprite"
		return info
	
	_is_high_kicking = true
	info["started"] = true
	
	# Play the kick animation
	var anim_name = rider_direction + "_kick"
	if _current_sprite.sprite_frames.has_animation(anim_name):
		_current_sprite.play(anim_name)
	
	high_kick_started.emit()
	
	# Wait for animation to complete
	await _current_sprite.animation_finished
	
	_is_high_kicking = false
	high_kick_complete.emit()
	
	return info


func get_high_kick_distance() -> int:
	"""Get the distance a bomb will travel when high-kicked by adult Tirra."""
	return _high_kick_distance + int(current_level) # 4 + 2 = 6 for adult


func is_high_kicking() -> bool:
	"""Check if currently performing high kick action."""
	return _is_high_kicking
