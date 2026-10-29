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
	var room_options := {}
	for arg in OS.get_cmdline_user_args():
		var option: String = arg.get_slice("=", 0)
		if option in ["--room-seats", "--room-preset-limit", "--room-map"]:
			if not "=" in arg or room_options.has(option):
				return {"error": "Duplicate or missing value for " + option}
			room_options[option] = true
			var value := arg.substr(option.length() + 1)
			if option == "--room-map":
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
	return {"role": role, "port": port, "room_seats": room_seats, "room_preset_limit": preset_limit, "room_map": room_map, "error": ""}
