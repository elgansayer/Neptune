extends SceneTree

## Trusted author-time conversion only. Source scenes may execute code on load.
const Manifest = preload("res://shared/content/pack_manifest.gd")
const Characters = preload("res://shared/content/character_pack_loader.gd")
const Definitions = preload("res://shared/content/arena_pack_loader.gd")

func _initialize() -> void:
	# Read the explicitly selected source before game autoloads mount the default
	# player pack and its .remap files. This process needs no game singletons.
	_export()

func _refuse(message: String) -> void:
	printerr("Character export refused: " + message)
	quit(1)

func _plain(node: Node2D) -> bool:
	return node.get_script() == null and node.position == Vector2.ZERO and node.scale == Vector2.ONE and node.rotation == 0 and node.skew == 0 and node.modulate == Color.WHITE and node.self_modulate == Color.WHITE and node.material == null and node.visible and node.z_index == 0

func _export() -> void:
	var options := {"--scene": "res://player.tscn", "--fallback": "state_idle"}
	var seen := {}
	for argument in OS.get_cmdline_user_args():
		var key := argument.get_slice("=", 0)
		if key not in ["--trusted-pck", "--output", "--id", "--version", "--author", "--license", "--provenance", "--name", "--scene", "--fallback"] or not "=" in argument or seen.has(key):
			_refuse("Unknown, duplicate or incomplete option: " + key)
			return
		seen[key] = true
		options[key] = argument.substr(key.length() + 1)
	for key in ["--trusted-pck", "--output", "--id", "--version", "--author", "--license", "--provenance", "--name"]:
		if not options.has(key) or options[key].is_empty():
			_refuse("Required option: " + key)
			return
	if not Manifest._text(options["--provenance"], 512):
		_refuse("Provenance must be nonblank bounded text")
		return
	var output: String = options["--output"]
	var manifest_path := output.path_join("manifest.json")
	if not Manifest.valid_manifest_path(manifest_path):
		_refuse("Output must be a portable res:// or user:// directory")
		return
	if DirAccess.dir_exists_absolute(output) or FileAccess.file_exists(output):
		_refuse("Output already exists; choose a new version directory")
		return
	var content_id: String = options["--id"].get_slice(":", 0) + ":character"
	var manifest := {"schema": Manifest.SCHEMA, "pack_id": options["--id"], "version": options["--version"],
		"author": options["--author"], "license": options["--license"], "dependencies": [],
		"content": [{"id": content_id, "kind": "character", "path": "character.json", "sha256": "0".repeat(64)}]}
	var checked := Manifest.validate(manifest)
	if not checked.accepted:
		_refuse(JSON.stringify(checked))
		return
	var source: String = options["--trusted-pck"]
	if not FileAccess.file_exists(source) or not ProjectSettings.load_resource_pack(source, true):
		_refuse("Cannot mount explicitly trusted source")
		return
	var scene = ResourceLoader.load(options["--scene"], "PackedScene", ResourceLoader.CACHE_MODE_IGNORE_DEEP)
	if not scene is PackedScene:
		_refuse("Trusted visual scene is missing")
		return
	var actor: Node = scene.instantiate()
	var sprite := actor.get_node_or_null("AnimatedSprite2D") as AnimatedSprite2D
	if actor.get_class() != "Node2D" or actor.get_child_count() != 1 or sprite == null or sprite.get_child_count() != 0 or not _plain(actor) or not _plain(sprite) or sprite.sprite_frames == null:
		actor.free()
		_refuse("Require one plain script-free AnimatedSprite2D; unsupported source transforms/materials cannot be preserved")
		return
	var frames: SpriteFrames = sprite.sprite_frames
	var definition := {"schema": Characters.SCHEMA, "name": options["--name"],
		"offset": [sprite.offset.x, sprite.offset.y], "centered": sprite.centered,
		"flip_h": sprite.flip_h, "flip_v": sprite.flip_v, "fallback": options["--fallback"],
		"provenance": {"description": options["--provenance"], "source_sha256": FileAccess.get_sha256(source)}, "animations": []}
	var pixels := {}
	var count := 0
	var names := frames.get_animation_names()
	if names.size() > Characters.MAX_ANIMATIONS:
		actor.free()
		_refuse("Source exceeds animation budget")
		return
	for name in names:
		var animation := {"name": str(name), "fps": frames.get_animation_speed(name), "loop": frames.get_animation_loop(name), "frames": []}
		count += frames.get_frame_count(name)
		if count > Characters.MAX_FRAMES:
			actor.free()
			_refuse("Source exceeds frame budget")
			return
		for index in frames.get_frame_count(name):
			var texture := frames.get_frame_texture(name, index)
			if texture == null or texture.get_width() > Characters.MAX_SIDE or texture.get_height() > Characters.MAX_SIDE:
				actor.free()
				_refuse("Source frame missing or exceeds dimensions")
				return
			var image := texture.get_image()
			if image == null or image.is_empty() or image.is_compressed() or image.has_mipmaps() or image.get_format() not in [Image.FORMAT_RGBA8, Image.FORMAT_RGB8, Image.FORMAT_L8, Image.FORMAT_LA8]:
				actor.free()
				_refuse("Source frame requires a plain decoded 8-bit image")
				return
			image.convert(Image.FORMAT_RGBA8)
			var bytes := image.get_data()
			var digest := Definitions._digest(bytes)
			var relative := "frames/%dx%d-%s.rgba" % [image.get_width(), image.get_height(), digest]
			pixels[relative] = bytes
			animation.frames.append({"path": relative, "sha256": digest, "width": image.get_width(), "height": image.get_height(), "duration": frames.get_frame_duration(name, index)})
		definition.animations.append(animation)
	checked = Characters.validate(definition)
	var text := JSON.stringify(definition, "  ", true, true) + "\n"
	if not checked.accepted or text.to_utf8_buffer().size() > Manifest.MAX_MANIFEST_BYTES:
		actor.free()
		_refuse("Invalid or oversized character definition: " + JSON.stringify(checked))
		return
	var original_presentation := Characters.presentation_hash(frames)
	actor.free()
	if DirAccess.make_dir_recursive_absolute(output.path_join("frames")) != OK:
		_refuse("Cannot create output")
		return
	for relative in pixels:
		var file := FileAccess.open(output.path_join(relative), FileAccess.WRITE)
		if file == null:
			_refuse("Cannot write frame pixels")
			return
		file.store_buffer(pixels[relative])
		file.close()
	var file := FileAccess.open(output.path_join("character.json"), FileAccess.WRITE)
	if file == null:
		_refuse("Cannot write character definition")
		return
	file.store_string(text)
	file.close()
	manifest.content[0].sha256 = FileAccess.get_sha256(output.path_join("character.json"))
	file = FileAccess.open(manifest_path, FileAccess.WRITE)
	if file == null:
		_refuse("Cannot write character manifest")
		return
	file.store_string(JSON.stringify(manifest, "  ", true, true) + "\n")
	file.close()
	var loaded := Characters.load_character([manifest_path], content_id)
	if not loaded.accepted or loaded.presentation_sha256 != original_presentation:
		_refuse("Exported presentation differs from trusted source: " + JSON.stringify(loaded.get("reason", "presentation_mismatch")))
		return
	print("NEPTUNE_CHARACTER_EXPORT=" + JSON.stringify({"accepted": true, "manifest": manifest_path,
		"descriptor": loaded.descriptor, "animations": loaded.frames.get_animation_names().size(),
		"frame_uses": count, "pixel_bytes": checked.pixel_bytes, "presentation_sha256": original_presentation}))
	quit(0)
