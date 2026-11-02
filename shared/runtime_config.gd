extends RefCounted

const Defaults = preload("res://shared/constants.gd")

## Process role is independent of rendering, including browser/headless clients.
static func read() -> Dictionary:
	var scene: String = ProjectSettings.get_setting("application/run/main_scene", "")
	for arg in OS.get_cmdline_args():
		if arg.ends_with(".tscn"):
			scene = arg
	return parse_arguments(OS.get_cmdline_user_args(), scene, "websocket" if OS.has_feature("web") else "enet")

## Kept separate from process arguments so the real startup contract is testable.
static func parse_arguments(arguments: Array, scene: String = "", default_transport: String = "enet") -> Dictionary:
	var role := "client"
	if scene.get_file() == "main_server.tscn":
		role = "server"
	elif scene.get_file() == "bot_test_runner.tscn":
		role = "test"
	var port: int = Defaults.SERVER_PORT
	var transport := default_transport
	var explicit_transport := false
	var explicit_role := false
	var explicit_port := false
	var room_seats := 0 # Omitted means choose the supported map/preset capacity.
	var preset_limit := Defaults.MAX_MATCH_SEATS
	var room_map := ""
	var room_pack_paths: Array = []
	var room_arena := ""
	var fill_to := 0
	var bot_personality := "BALANCED"
	var room_options := {}
	for arg in arguments:
		if not arg is String:
			return {"error": "Runtime arguments must be strings"}
		var option: String = arg.get_slice("=", 0)
		if option == "--room-pack":
			if not "=" in arg:
				return {"error": "Missing value for --room-pack"}
			var path: String = arg.substr(option.length() + 1)
			if not _valid_pack_manifest_path(path):
				return {"error": "Invalid --room-pack; use a normalized local res:// or user:// JSON manifest"}
			if path in room_pack_paths:
				return {"error": "Duplicate --room-pack manifest: " + path}
			if room_pack_paths.size() >= 32:
				return {"error": "Too many --room-pack manifests; maximum is 32"}
			room_pack_paths.append(path)
			continue
		if option in ["--room-seats", "--room-preset-limit", "--room-map", "--room-fill-to", "--room-bot-personality", "--room-arena"]:
			if not "=" in arg or room_options.has(option):
				return {"error": "Duplicate or missing value for " + option}
			room_options[option] = true
			var value: String = arg.substr(option.length() + 1)
			if option == "--room-arena":
				if not _valid_content_id(value):
					return {"error": "Invalid --room-arena; use a namespaced namespace:name identifier"}
				room_arena = value
			elif option == "--room-bot-personality":
				if value.is_empty() or value.length() > 32:
					return {"error": "Invalid --room-bot-personality"}
				bot_personality = value # Authority validates actual supported profiles.
			elif option == "--room-fill-to":
				if not value.is_valid_int() or value.to_int() < 0 or value.to_int() > Defaults.MAX_MATCH_SEATS:
					return {"error": "Invalid --room-fill-to; use 0..12"}
				fill_to = value.to_int()
			elif option == "--room-map":
				if not value.begins_with("res://maps/") or not value.ends_with(".json") or ".." in value or value.length() > 256:
					return {"error": "Invalid --room-map; use a local res://maps/*.json resource"}
				room_map = value
			else:
				if not value.is_valid_int() or value.to_int() < 1 or value.to_int() > Defaults.MAX_MATCH_SEATS:
					return {"error": "Invalid " + option + "; use 1..12"}
				if option == "--room-seats": room_seats = value.to_int()
				else: preset_limit = value.to_int()
			continue
		if arg.begins_with("--transport="):
			if explicit_transport:
				return {"error": "Duplicate --transport"}
			explicit_transport = true
			transport = arg.trim_prefix("--transport=")
			if transport not in ["enet", "websocket"]:
				return {"error": "Invalid --transport; use enet or websocket"}
		elif arg == "--transport":
			return {"error": "Runtime options require =value"}
		elif arg.begins_with("--runtime-role="):
			if explicit_role:
				return {"error": "Duplicate --runtime-role"}
			explicit_role = true
			role = arg.trim_prefix("--runtime-role=")
			if role not in ["server", "client", "test"]:
				return {"error": "Invalid --runtime-role; use server, client or test"}
		elif arg.begins_with("--server-port="):
			if explicit_port:
				return {"error": "Duplicate --server-port"}
			explicit_port = true
			var value: String = arg.trim_prefix("--server-port=")
			if not value.is_valid_int() or value.to_int() < 1024 or value.to_int() > 65535:
				return {"error": "Invalid --server-port; use 1024..65535"}
			port = value.to_int()
		elif arg == "--runtime-role" or arg == "--server-port":
			return {"error": "Runtime options require =value"}
	if room_seats > preset_limit:
		return {"error": "Room seats exceed preset limit"}
	if room_pack_paths.is_empty() != room_arena.is_empty():
		return {"error": "--room-pack and --room-arena must be supplied together"}
	if not room_pack_paths.is_empty() and not room_map.is_empty():
		return {"error": "Choose --room-map or --room-pack/--room-arena, not both"}
	return {"role": role, "port": port, "transport": transport, "room_seats": room_seats, "room_preset_limit": preset_limit, "room_map": room_map, "room_pack_paths": room_pack_paths, "room_arena": room_arena, "room_fill_to": fill_to, "room_bot_personality": bot_personality, "error": ""}

static func _valid_pack_manifest_path(path: String) -> bool:
	return preload("res://shared/content/pack_manifest.gd").valid_manifest_path(path)

static func _valid_content_id(value: String) -> bool:
	return preload("res://shared/content/pack_manifest.gd").valid_id(value)
