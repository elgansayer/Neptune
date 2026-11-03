extends Control

# Simple login screen

@onready var username_field = $VBoxContainer/UsernameField
@onready var password_field = $VBoxContainer/PasswordField
@onready var login_button = $VBoxContainer/LoginButton
@onready var register_button = $VBoxContainer/RegisterButton
@onready var status_label = $VBoxContainer/StatusLabel

var client_main
var cancel_content_button: Button

func _ready():
	# Get reference to main client
	client_main = get_node("/root/ClientMain")
	
	# Connect signals
	client_main.connection_succeeded.connect(_on_connection_succeeded)
	client_main.connection_failed.connect(_on_connection_failed)
	client_main.authentication_succeeded.connect(_on_authentication_succeeded)
	client_main.authentication_failed.connect(_on_authentication_failed)
	client_main.content_status_changed.connect(_on_content_status)
	
	login_button.pressed.connect(_on_login_pressed)
	register_button.pressed.connect(_on_register_pressed)
	cancel_content_button = Button.new()
	cancel_content_button.text = "Cancel download"
	cancel_content_button.visible = false
	$VBoxContainer.add_child(cancel_content_button)
	cancel_content_button.pressed.connect(func(): client_main.cancel_content_download())
	
	status_label.text = "Connecting..."
	
	# Auto-connect to localhost
	client_main.connect_to_server("127.0.0.1")
	
	# Generate random username for testing
	var random_name = "Player_" + str(randi() % 10000)
	username_field.text = random_name
	password_field.text = "password123"
	
	# Hide login fields for now (will use PlayFab later)
	$VBoxContainer/Title.text = "Connecting to Server..."
	username_field.visible = false
	password_field.visible = false
	login_button.visible = false
	register_button.visible = false

func _on_login_pressed():
	if client_main.last_connection_error in ["release_revision_mismatch_reload_required", "incompatible_protocol_versions", "invalid_protocol_offer"] and OS.has_feature("web"):
		JavaScriptBridge.eval("window.location.reload()")
		return
	login_button.visible = false
	if not client_main.connected:
		status_label.text = "Connecting..."
		client_main.connect_to_server(client_main.server_address)
		return
	var username = username_field.text.strip_edges()
	var password = password_field.text
	
	if username.is_empty() or password.is_empty():
		status_label.text = "Enter username and password"
		return
	
	status_label.text = "Logging in..."
	client_main.login(username, password)

func _on_register_pressed():
	var username = username_field.text.strip_edges()
	var password = password_field.text
	
	if username.is_empty() or password.is_empty():
		status_label.text = "Enter username and password"
		return
	
	status_label.text = "Registering..."
	client_main.register(username, password)

func _on_connection_succeeded():
	$VBoxContainer/Title.text = "Joining Game..."
	status_label.text = "Connected! Registering..."
	# Auto-register with random credentials
	var username = username_field.text
	var password = password_field.text
	client_main.register(username, password)
	# Small delay then login
	await get_tree().create_timer(0.2).timeout
	status_label.text = "Logging in..."
	client_main.login(username, password)

func _on_connection_failed():
	cancel_content_button.visible = false
	login_button.text = "Try again"
	login_button.visible = true
	var reason: String = client_main.last_connection_error
	match reason:
		"release_revision_mismatch_reload_required":
			login_button.text = "Reload latest build"
			status_label.text = "The server has updated. Reload to join the matching build."
		"incompatible_protocol_versions":
			login_button.text = "Reload latest build" if OS.has_feature("web") else "Try again"
			status_label.text = "Game versions are incompatible. Reload the browser or update the client."
		"invalid_protocol_offer", "protocol_offer_too_large", "protocol_not_negotiated":
			login_button.text = "Reload latest build" if OS.has_feature("web") and reason == "invalid_protocol_offer" else "Try again"
			status_label.text = "Compatibility check failed. Reload the browser or choose a compatible Neptune server."
		"protocol_handshake_timeout_or_disconnect":
			status_label.text = "Compatibility check timed out or the server disconnected. Try again."
		_:
			status_label.text = "Could not connect to the server. Try again."

func _on_authentication_succeeded():
	cancel_content_button.visible = false
	login_button.visible = false
	status_label.text = "Login successful!"
	# Load game view
	await get_tree().create_timer(0.5).timeout
	get_tree().change_scene_to_file("res://client/game_view.tscn")

func _on_authentication_failed(error: String):
	$VBoxContainer/Title.text = "Unable to Join"
	cancel_content_button.visible = false
	login_button.text = "Try again"
	login_button.visible = true
	match error:
		"content_cancelled":
			status_label.text = "Download cancelled. Choose Try again when you are ready."
		"content_download_timeout":
			status_label.text = "The server content download timed out. Try again."
		"round_finished":
			status_label.text = "The previous round has ended. Choose Try again to join a new round."
		"room_full":
			status_label.text = "This server is full. Try again or choose another server."
		_:
			if error.begins_with("content_") or error.begins_with("unexpected_content_") or error.begins_with("invalid_content_") or error.begins_with("stale_content_"):
				status_label.text = "Server content could not be verified. Try again or choose another server."
			else:
				status_label.text = "Login failed: " + error

func _on_content_status(result: Dictionary) -> void:
	match result.get("state", ""):
		"downloading":
			login_button.visible = false
			cancel_content_button.visible = true
			status_label.text = "Preparing server content: %d / %d KiB received, %d packs cached" % [
				ceili(float(result.get("received_bytes", 0)) / 1024.0),
				ceili(float(result.get("total_bytes", 0)) / 1024.0), result.get("cache_hits", 0)]
		"ready":
			cancel_content_button.visible = false
			status_label.text = "Server content verified. Joining..."
