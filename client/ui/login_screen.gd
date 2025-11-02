extends Control

# Simple login screen

@onready var username_field = $VBoxContainer/UsernameField
@onready var password_field = $VBoxContainer/PasswordField
@onready var login_button = $VBoxContainer/LoginButton
@onready var register_button = $VBoxContainer/RegisterButton
@onready var status_label = $VBoxContainer/StatusLabel

var client_main

func _ready():
	# Get reference to main client
	client_main = get_node("/root/ClientMain")
	
	# Connect signals
	client_main.connection_succeeded.connect(_on_connection_succeeded)
	client_main.connection_failed.connect(_on_connection_failed)
	client_main.authentication_succeeded.connect(_on_authentication_succeeded)
	client_main.authentication_failed.connect(_on_authentication_failed)
	
	login_button.pressed.connect(_on_login_pressed)
	register_button.pressed.connect(_on_register_pressed)
	
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
	status_label.text = "Connection failed!"

func _on_authentication_succeeded():
	status_label.text = "Login successful!"
	# Load game view
	await get_tree().create_timer(0.5).timeout
	get_tree().change_scene_to_file("res://client/game_view.tscn")

func _on_authentication_failed(error: String):
	status_label.text = "Login failed: " + error
