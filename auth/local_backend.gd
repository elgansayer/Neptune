extends Node

# Local in-memory authentication
# TODO: Replace with SQLite using GodotSQLite addon
# This is used for development/testing before migrating to PlayFab

var users = {}  # username -> {password_hash: String, created_at: String}

func _ready():
	print("[LocalBackend] In-memory auth initialized")
	print("[LocalBackend] WARNING: Data will not persist between restarts!")
	print("[LocalBackend] TODO: Install GodotSQLite addon for persistence")

func authenticate(username: String, password: String) -> Dictionary:
	if username.is_empty() or password.is_empty():
		return {"success": false, "error": "Username and password required"}
	
	if not users.has(username):
		return {"success": false, "error": "User not found"}
	
	var stored_hash = users[username].password_hash
	var password_hash = password.md5_text()  # Simple hash for now
	
	if stored_hash == password_hash:
		return {"success": true, "user_id": username}
	else:
		return {"success": false, "error": "Invalid password"}

func register_user(username: String, password: String) -> Dictionary:
	if username.is_empty() or password.is_empty():
		return {"success": false, "error": "Username and password required"}
	
	if username.length() < 3:
		return {"success": false, "error": "Username must be at least 3 characters"}
	
	if password.length() < 6:
		return {"success": false, "error": "Password must be at least 6 characters"}
	
	if users.has(username):
		return {"success": false, "error": "Username already taken"}
	
	# Hash password and store
	var password_hash = password.md5_text()
	users[username] = {
		"password_hash": password_hash,
		"created_at": Time.get_datetime_string_from_system()
	}
	
	print("[LocalBackend] Registered user: ", username)
	return {"success": true}
