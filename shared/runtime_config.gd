extends RefCounted

const Defaults = preload("res://shared/constants.gd")

## Process role is independent of rendering, including browser/headless clients.
static func read() -> Dictionary:
	var scene: String = ProjectSettings.get_setting("application/run/main_scene", "")
	for arg in OS.get_cmdline_args():
		if arg.ends_with(".tscn"):
			scene = arg
	var role := "client"
	if scene.get_file() == "main_server.tscn":
		role = "server"
	elif scene.get_file() == "bot_test_runner.tscn":
		role = "test"
	var port: int = Defaults.SERVER_PORT
	var explicit_role := false
	var explicit_port := false
	var room_seats := 0 # Omitted means choose the supported map/preset capacity.
	var preset_limit := Defaults.MAX_MATCH_SEATS
	var room_map := ""
	var room_pack := ""
	var room_map_id := ""
	var fill_to := 0
	var bot_personality := "BALANCED"
	var room_options := {}
	for arg in OS.get_cmdline_user_args():
		var option: String = arg.get_slice("=", 0)
		if option in ["--room-seats", "--room-preset-limit", "--room-map", "--room-pack", "--room-map-id", "--room-fill-to", "--room-bot-personality"]:
			if not "=" in arg or room_options.has(option):
				return {"error": "Duplicate or missing value for " + option}
			room_options[option] = true
			var value := arg.substr(option.length() + 1)
			if option == "--room-pack":
				if value.is_empty() or value.length() > 512 or ".." in value or "\\" in value or not value.is_absolute_path():
					return {"error": "Invalid --room-pack; use an absolute, res:// or user:// local directory"}
				room_pack = value
			elif option == "--room-map-id":
				if value.is_empty() or value.length() > 161:
					return {"error": "Invalid --room-map-id"}
				room_map_id = value
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
		if arg.begins_with("--runtime-role="):
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
	if room_pack.is_empty() != room_map_id.is_empty() or (not room_pack.is_empty() and not room_map.is_empty()):
		return {"error": "Use --room-pack and --room-map-id together, without --room-map"}
	return {"role": role, "port": port, "room_seats": room_seats, "room_preset_limit": preset_limit, "room_map": room_map, "room_pack": room_pack, "room_map_id": room_map_id, "room_fill_to": fill_to, "room_bot_personality": bot_personality, "error": ""}
