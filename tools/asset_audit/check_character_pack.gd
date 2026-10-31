extends SceneTree

## Author-time check for trusted local character projects/exports, not a sandbox.
## Run with --path <project> --script <absolute path to this file> -- [options].

func fail(message: String) -> void:
	push_error(message)
	quit(1)

func _initialize() -> void:
	var scene_path := "res://player.tscn"
	var sprite_path := "AnimatedSprite2D"
	var pack_path := ""
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--scene="):
			scene_path = argument.trim_prefix("--scene=")
		elif argument.begins_with("--sprite="):
			sprite_path = argument.trim_prefix("--sprite=")
		elif argument.begins_with("--pack="):
			pack_path = argument.trim_prefix("--pack=")
		else:
			fail("Unknown character check argument: " + argument)
			return
	if not pack_path.is_empty() and not ProjectSettings.load_resource_pack(pack_path, false):
		fail("Cannot mount trusted character export: " + pack_path)
		return
	var resource = load(scene_path)
	if not resource is PackedScene:
		fail("Character scene missing or invalid: " + scene_path)
		return
	var actor = resource.instantiate()
	var sprite = actor.get_node_or_null(NodePath(sprite_path))
	if not sprite is AnimatedSprite2D or sprite.sprite_frames == null:
		actor.free()
		fail("Character must contain an AnimatedSprite2D with SpriteFrames")
		return
	var frames: SpriteFrames = sprite.sprite_frames
	var names := frames.get_animation_names()
	var records := []
	if names.is_empty():
		actor.free()
		fail("Character has no animations")
		return
	for animation in names:
		if frames.get_frame_count(animation) < 1:
			actor.free()
			fail("Character animation has no frames: " + str(animation))
			return
		for index in frames.get_frame_count(animation):
			var texture := frames.get_frame_texture(animation, index)
			var image: Image = texture.get_image() if texture != null else null
			if image == null or image.is_empty():
				actor.free()
				fail("Character frame texture is missing: " + str(animation))
				return
			image.convert(Image.FORMAT_RGBA8)
			var context := HashingContext.new()
			context.start(HashingContext.HASH_SHA256)
			context.update(image.get_data())
			records.append([str(animation), index, frames.get_animation_speed(animation),
				frames.get_animation_loop(animation), frames.get_frame_duration(animation, index),
				image.get_size(), context.finish().hex_encode()])
	print(JSON.stringify({"animations": names.size(), "frame_uses": records.size(),
		"sprite_offset": str(sprite.offset), "engine": Engine.get_version_info().string,
		"presentation_sha256": JSON.stringify(records).sha256_text()}))
	actor.free()
	quit(0)
