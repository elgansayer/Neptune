extends SceneTree

## Author-time only: trusted PCK scenes may execute code. Never run on downloads.
const Manifest = preload("res://shared/content/pack_manifest.gd")
const Registry = preload("res://shared/content/pack_registry.gd")
const Maps = preload("res://shared/maps/map_loader.gd")
const Legacy = preload("res://shared/maps/map_pack_loader.gd")

func _initialize() -> void:
	call_deferred("_export")

func _refuse(message: String) -> void:
	printerr("Map export refused: " + message)
	quit(1)

func _export() -> void:
	var options := {}
	for argument in OS.get_cmdline_user_args():
		var key := argument.get_slice("=", 0)
		if key not in ["--trusted-pck", "--output", "--id", "--version", "--author", "--license", "--provenance"] or not "=" in argument or options.has(key):
			_refuse("Unknown, duplicate or incomplete option: " + key)
			return
		options[key] = argument.substr(key.length() + 1)
	for key in ["--trusted-pck", "--output", "--id", "--version", "--author", "--license", "--provenance"]:
		if not options.has(key) or options[key].is_empty():
			_refuse("Required option: " + key)
			return
	var output: String = options["--output"]
	# Author exports create a new directory; immutable selected packs are never rewritten.
	if DirAccess.dir_exists_absolute(output) or FileAccess.file_exists(output):
		_refuse("Output already exists; choose a new version directory")
		return
	var manifest := {"schema": Manifest.SCHEMA, "id": options["--id"], "version": options["--version"],
		"author": options["--author"], "license": options["--license"], "provenance": options["--provenance"],
		"dependencies": [], "content": [{"id": options["--id"] + ":arena", "type": "map", "path": "arena.json", "sha256": "0".repeat(64)}]}
	var valid := Manifest.validate(manifest)
	if not valid.ok:
		_refuse(JSON.stringify(valid.error))
		return
	var native := Legacy.load_map_from_pck(options["--trusted-pck"])
	if native.is_empty() or native.tile_size != 16:
		_refuse("Trusted source could not be converted, or uses an unsupported tile size")
		return
	if DirAccess.make_dir_recursive_absolute(output) != OK:
		_refuse("Cannot create output directory")
		return
	var map_path := output.path_join("arena.json")
	if not Maps.save_map_to_file(native, map_path):
		_refuse("Cannot export map JSON")
		return
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(map_path))
	data["schema"] = "neptune.map/1"
	valid = Registry.validate_map(data, map_path)
	if not valid.ok:
		_refuse(JSON.stringify(valid.error))
		return
	var file := FileAccess.open(map_path, FileAccess.WRITE)
	file.store_string(JSON.stringify(data, "  ") + "\n")
	file.close()
	manifest.content[0].sha256 = FileAccess.get_sha256(map_path)
	file = FileAccess.open(output.path_join("pack.json"), FileAccess.WRITE)
	file.store_string(JSON.stringify(manifest, "  ") + "\n")
	file.close()
	var registry := Registry.new()
	var registered := registry.register_directory(output)
	if not registered.ok:
		_refuse(JSON.stringify(registered.error))
		return
	print("NEPTUNE_MAP_EXPORT=" + JSON.stringify(registered))
	await process_frame # Flush the trusted legacy converter's queued scene cleanup.
	await process_frame
	quit(0)
