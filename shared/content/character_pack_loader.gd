extends RefCounted

## Visual data only. Never loads a scene/script/resource from a pack.
const Manifest = preload("res://shared/content/pack_manifest.gd")
const Definitions = preload("res://shared/content/arena_pack_loader.gd")
const SCHEMA := "neptune.character.v1"
const MAX_ANIMATIONS := 64
const MAX_FRAMES := 512
const MAX_IMAGES := 256
const MAX_SIDE := 256
const MAX_PIXEL_BYTES := 16 * 1024 * 1024

static func _number(value: Variant, minimum: float, maximum: float) -> bool:
	return (value is int or value is float) and is_finite(float(value)) and value >= minimum and value <= maximum

static func _name(value: Variant) -> bool:
	return value is String and RegEx.create_from_string("^[a-z][a-z0-9_]{0,63}\\z").search(value) != null

static func _image_path(value: Variant) -> bool:
	if not value is String or not value.ends_with(".rgba"):
		return false
	return Manifest.valid_path(value.trim_suffix(".rgba") + ".json")

static func validate(data: Variant, source: String = "") -> Dictionary:
	if not data is Dictionary: return Manifest.failure("character_not_object", "$", source)
	var shape := Manifest._keys(data, ["schema", "name", "offset", "centered", "flip_h", "flip_v", "fallback", "provenance", "animations"], "$", source)
	if not shape.accepted: return shape
	if data.schema != SCHEMA: return Manifest.failure("unsupported_character_schema", "schema", source)
	if not Manifest._text(data.name, 128): return Manifest.failure("invalid_character_name", "name", source)
	if not data.offset is Array or data.offset.size() != 2 or not _number(data.offset[0], -256, 256) or not _number(data.offset[1], -256, 256):
		return Manifest.failure("invalid_sprite_offset", "offset", source)
	for field in ["centered", "flip_h", "flip_v"]:
		if not data[field] is bool: return Manifest.failure("invalid_visual_flag", field, source)
	if not data.provenance is Dictionary: return Manifest.failure("invalid_provenance", "provenance", source)
	shape = Manifest._keys(data.provenance, ["description", "source_sha256"], "provenance", source)
	if not shape.accepted: return shape
	if not Manifest._text(data.provenance.description, 512) or not Manifest.valid_hash(data.provenance.source_sha256):
		return Manifest.failure("invalid_provenance", "provenance", source)
	if not data.animations is Array or data.animations.is_empty() or data.animations.size() > MAX_ANIMATIONS:
		return Manifest.failure("animation_budget_exceeded", "animations", source)
	var names := {}
	var images := {}
	var count := 0
	var pixel_bytes := 0
	for index in data.animations.size():
		var animation = data.animations[index]
		var field := "animations[%d]" % index
		if not animation is Dictionary: return Manifest.failure("invalid_animation", field, source)
		shape = Manifest._keys(animation, ["name", "fps", "loop", "frames"], field, source)
		if not shape.accepted: return shape
		if not _name(animation.name) or names.has(animation.name): return Manifest.failure("invalid_or_duplicate_animation", field + ".name", source)
		if not _number(animation.fps, 0.001, 240): return Manifest.failure("invalid_animation_speed", field + ".fps", source)
		if not animation.loop is bool: return Manifest.failure("invalid_animation_loop", field + ".loop", source)
		if not animation.frames is Array or animation.frames.is_empty(): return Manifest.failure("missing_frames", field + ".frames", source)
		count += animation.frames.size()
		if count > MAX_FRAMES: return Manifest.failure("frame_budget_exceeded", field + ".frames", source)
		names[animation.name] = true
		for frame_index in animation.frames.size():
			var frame = animation.frames[frame_index]
			var frame_field := field + ".frames[%d]" % frame_index
			if not frame is Dictionary: return Manifest.failure("invalid_frame", frame_field, source)
			shape = Manifest._keys(frame, ["path", "sha256", "width", "height", "duration"], frame_field, source)
			if not shape.accepted: return shape
			if not _image_path(frame.path): return Manifest.failure("invalid_pixel_path", frame_field + ".path", source)
			if not Manifest.valid_hash(frame.sha256): return Manifest.failure("invalid_hash", frame_field + ".sha256", source)
			if not Definitions._integer(frame.width) or not Definitions._integer(frame.height) or not _number(frame.width, 1, MAX_SIDE) or not _number(frame.height, 1, MAX_SIDE):
				return Manifest.failure("invalid_frame_dimensions", frame_field, source)
			if not _number(frame.duration, 0.001, 60): return Manifest.failure("invalid_frame_duration", frame_field + ".duration", source)
			var identity := {"sha256": frame.sha256, "width": int(frame.width), "height": int(frame.height)}
			if images.has(frame.path) and images[frame.path] != identity:
				return Manifest.failure("conflicting_pixel_reference", frame_field + ".path", source)
			if not images.has(frame.path):
				images[frame.path] = identity
				pixel_bytes += int(frame.width) * int(frame.height) * 4
				if images.size() > MAX_IMAGES or pixel_bytes > MAX_PIXEL_BYTES:
					return Manifest.failure("pixel_budget_exceeded", frame_field, source)
	if not _name(data.fallback) or not names.has(data.fallback): return Manifest.failure("missing_fallback_animation", "fallback", source)
	return {"accepted": true, "images": images, "frame_uses": count, "pixel_bytes": pixel_bytes}

static func load_character(manifest_paths: Array, content_id: String, expected_lock: Dictionary = {}) -> Dictionary:
	var definition := Definitions.load_definition(manifest_paths, content_id, "character", expected_lock)
	if not definition.accepted: return definition
	var checked := validate(definition.data, definition.source)
	if not checked.accepted: return checked
	var pixels := {}
	# Validate every exact-length payload before allocating image/visual resources.
	for relative in checked.images:
		var located := Definitions._definition_path(definition.root, relative)
		if not located.accepted: return located
		var file := FileAccess.open(located.path, FileAccess.READ)
		if file == null: return Manifest.failure("pixel_file_missing", relative, definition.source)
		var identity: Dictionary = checked.images[relative]
		var size: int = identity.width * identity.height * 4
		if file.get_length() != size: return Manifest.failure("pixel_byte_length_mismatch", relative, definition.source)
		var bytes := file.get_buffer(size)
		file.close()
		if bytes.size() != size or Definitions._digest(bytes) != identity.sha256:
			return Manifest.failure("pixel_hash_mismatch", relative, definition.source)
		pixels[relative] = bytes
	var textures := {}
	for relative in pixels:
		var identity: Dictionary = checked.images[relative]
		var image := Image.create_from_data(identity.width, identity.height, false, Image.FORMAT_RGBA8, pixels[relative])
		textures[relative] = ImageTexture.create_from_image(image)
	var frames := SpriteFrames.new()
	frames.remove_animation("default")
	for animation in definition.data.animations:
		frames.add_animation(animation.name)
		frames.set_animation_speed(animation.name, animation.fps)
		frames.set_animation_loop(animation.name, animation.loop)
		for frame in animation.frames:
			frames.add_frame(animation.name, textures[frame.path], frame.duration)
	return {"accepted": true, "reason": "character_loaded", "name": definition.data.name,
		"frames": frames, "offset": Vector2(definition.data.offset[0], definition.data.offset[1]),
		"centered": definition.data.centered, "flip_h": definition.data.flip_h, "flip_v": definition.data.flip_v,
		"fallback": definition.data.fallback, "provenance": definition.data.provenance.duplicate(true),
		"descriptor": definition.descriptor, "selection": definition.selection,
		"lock": definition.lock, "lock_sha256": definition.lock_sha256,
		"presentation_sha256": presentation_hash(frames)}

static func create_visual(character: Dictionary) -> Node2D:
	if not character.get("accepted", false) or not character.get("frames") is SpriteFrames: return null
	var root := Node2D.new()
	root.name = "CharacterVisual"
	var sprite := AnimatedSprite2D.new()
	sprite.name = "AnimatedSprite2D"
	sprite.sprite_frames = character.frames.duplicate(true)
	sprite.offset = character.offset
	sprite.centered = character.centered
	sprite.flip_h = character.flip_h
	sprite.flip_v = character.flip_v
	root.add_child(sprite)
	sprite.play(character.fallback)
	return root

static func presentation_hash(frames: SpriteFrames) -> String:
	# Same pixel/timing oracle used by the existing trusted authoring checker.
	var records := []
	for animation in frames.get_animation_names():
		for index in frames.get_frame_count(animation):
			var image := frames.get_frame_texture(animation, index).get_image()
			image.convert(Image.FORMAT_RGBA8)
			records.append([str(animation), index, frames.get_animation_speed(animation),
				frames.get_animation_loop(animation), frames.get_frame_duration(animation, index),
				image.get_size(), Definitions._digest(image.get_data())])
	return JSON.stringify(records).sha256_text()
