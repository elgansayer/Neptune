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
	for arg in OS.get_cmdline_user_args():
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
	return {"role": role, "port": port, "error": ""}
