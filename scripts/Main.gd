extends Control

# Menu panels
@onready var main_menu_panel = $MainContainer
@onready var create_match_panel = null
@onready var options_panel = null
@onready var status_label = $MainContainer/MarginContainer/VBoxContainer/StatusLabel

# CreateMatch controls
var mode_select: OptionButton
var map_select: OptionButton
var max_players_spinbox: SpinBox
var time_limit_select: OptionButton
var win_condition_select: OptionButton
var enable_powerups_checkbox: CheckBox
var enable_skull_bombs_checkbox: CheckBox

# Options controls
var music_volume_slider: HSlider
var sfx_volume_slider: HSlider
var resolution_select: OptionButton
var fullscreen_checkbox: CheckBox


func _ready():
	# Load sub-menu scenes
	var create_match_scene = load("res://CreateMatch.tscn")
	var options_scene = load("res://Options.tscn")
	
	# Instance them as children
	create_match_panel = create_match_scene.instantiate()
	options_panel = options_scene.instantiate()
	add_child(create_match_panel)
	add_child(options_panel)
	
	# Get references to CreateMatch controls
	mode_select = create_match_panel.get_node("MarginContainer/VBoxContainer/ModeSelect")
	map_select = create_match_panel.get_node("MarginContainer/VBoxContainer/MapSelect")
	max_players_spinbox = create_match_panel.get_node("MarginContainer/VBoxContainer/MaxPlayersSpinBox")
	time_limit_select = create_match_panel.get_node("MarginContainer/VBoxContainer/TimeLimitSelect")
	win_condition_select = create_match_panel.get_node("MarginContainer/VBoxContainer/WinConditionSelect")
	enable_powerups_checkbox = create_match_panel.get_node("MarginContainer/VBoxContainer/EnablePowerupsCheckBox")
	enable_skull_bombs_checkbox = create_match_panel.get_node("MarginContainer/VBoxContainer/EnableSkullBombsCheckBox")
	
	# Populate CreateMatch dropdowns
	mode_select.add_item("Classic")
	mode_select.add_item("Team Battle")
	mode_select.add_item("Survival")
	mode_select.add_item("Capture the Flag")
	mode_select.selected = 0
	
	map_select.add_item("Classic Arena")
	map_select.add_item("Desert Storm")
	map_select.add_item("Ice Palace")
	map_select.selected = 0
	
	time_limit_select.add_item("3 Minutes")
	time_limit_select.add_item("5 Minutes")
	time_limit_select.add_item("Unlimited")
	time_limit_select.selected = 1
	
	win_condition_select.add_item("Last Man Standing (Lives)")
	win_condition_select.add_item("Best of Rounds")
	win_condition_select.selected = 0
	
	# Connect CreateMatch buttons
	create_match_panel.get_node("MarginContainer/VBoxContainer/ButtonsContainer/HostGameButton").pressed.connect(_on_host_game_pressed)
	create_match_panel.get_node("MarginContainer/VBoxContainer/ButtonsContainer/JoinGameButton").pressed.connect(_on_join_game_pressed)
	create_match_panel.get_node("MarginContainer/VBoxContainer/ButtonsContainer/BackButton").pressed.connect(_on_create_match_back_pressed)
	
	# Get references to Options controls
	music_volume_slider = options_panel.get_node("MarginContainer/VBoxContainer/MusicVolumeSlider")
	sfx_volume_slider = options_panel.get_node("MarginContainer/VBoxContainer/SFXVolumeSlider")
	resolution_select = options_panel.get_node("MarginContainer/VBoxContainer/ResolutionSelect")
	fullscreen_checkbox = options_panel.get_node("MarginContainer/VBoxContainer/FullscreenCheckBox")
	
	# Populate Options dropdowns
	resolution_select.add_item("640 x 480")
	resolution_select.add_item("800 x 600")
	resolution_select.add_item("1024 x 768")
	resolution_select.selected = 1
	
	# Connect Options buttons
	options_panel.get_node("MarginContainer/VBoxContainer/ControlButtonsContainer/ConfigureControlsButton").pressed.connect(_on_configure_controls_pressed)
	options_panel.get_node("MarginContainer/VBoxContainer/ControlButtonsContainer/ResetControlsButton").pressed.connect(_on_reset_controls_pressed)
	options_panel.get_node("MarginContainer/VBoxContainer/BackButton").pressed.connect(_on_options_back_pressed)
	
	# Connect Options value changes
	music_volume_slider.value_changed.connect(_on_music_volume_changed)
	sfx_volume_slider.value_changed.connect(_on_sfx_volume_changed)
	resolution_select.item_selected.connect(_on_resolution_selected)
	fullscreen_checkbox.toggled.connect(_on_fullscreen_toggled)


# Main Menu button handlers
func _on_start_game_pressed():
	status_label.text = "Connecting to server..."
	
	# Initialize Nakama client if not already done
	if not NakamaService.client:
		if not NakamaService.init_client():
			status_label.text = "Failed to initialize client"
			return
	
	# Authenticate with device ID
	if not NakamaService.session:
		status_label.text = "Authenticating..."
		await NakamaService.authenticate_device("player_" + str(OS.get_unique_id()))
		
		if not NakamaService.session:
			status_label.text = "Authentication failed"
			return
	
	# Start matchmaking
	status_label.text = "Finding match..."
	await NakamaService.start_matchmaking("*", 2, 4)
	
	if NakamaService.match_id:
		status_label.text = "Match found! Loading..."
		await get_tree().create_timer(0.5).timeout
		get_tree().change_scene_to_file("res://Game.tscn")
	else:
		status_label.text = "Failed to find match"


func _on_create_match_pressed():
	main_menu_panel.visible = false
	create_match_panel.visible = true
	status_label.text = "Create/Join Match"


func _on_training_pressed():
	status_label.text = "Loading training mode..."
	await get_tree().create_timer(0.5).timeout
	# TODO: Load training scene with AI opponents
	print("Training mode not yet implemented")
	status_label.text = "Training - Coming Soon!"


func _on_customise_pressed():
	get_tree().change_scene_to_file("res://CharacterSelect.tscn")


func _on_options_pressed():
	main_menu_panel.visible = false
	options_panel.visible = true
	status_label.text = "Options"


func _on_credits_pressed():
	status_label.text = "Credits: Bomberman Clone v0.1 | Built with Godot 4"
	await get_tree().create_timer(3.0).timeout
	status_label.text = "Idle"


func _on_exit_pressed():
	status_label.text = "Exiting..."
	await get_tree().create_timer(0.3).timeout
	get_tree().quit()


# CreateMatch menu handlers
func _on_host_game_pressed():
	status_label.text = "Connecting to server..."
	
	# Initialize Nakama client if not already done
	if not NakamaService.client:
		if not NakamaService.init_client():
			status_label.text = "Failed to initialize client"
			return
	
	# Authenticate with device ID
	if not NakamaService.session:
		status_label.text = "Authenticating..."
		await NakamaService.authenticate_device("player_" + str(OS.get_unique_id()))
		
		if not NakamaService.session:
			status_label.text = "Authentication failed"
			return
	
	status_label.text = "Creating match..."
	var game_mode = mode_select.get_item_text(mode_select.selected)
	var map_name = map_select.get_item_text(map_select.selected)
	var max_players = max_players_spinbox.value
	print("Hosting: ", game_mode, " on ", map_name, " (max ", max_players, " players)")
	
	# Start matchmaking (creates match via RPC)
	await NakamaService.start_matchmaking("*", 2, int(max_players))
	
	if NakamaService.match_id:
		status_label.text = "Match created! Loading..."
		await get_tree().create_timer(0.5).timeout
		get_tree().change_scene_to_file("res://Game.tscn")
	else:
		status_label.text = "Failed to create match"


func _on_join_game_pressed():
	status_label.text = "Connecting to server..."
	
	# Initialize Nakama client if not already done
	if not NakamaService.client:
		if not NakamaService.init_client():
			status_label.text = "Failed to initialize client"
			return
	
	# Authenticate with device ID
	if not NakamaService.session:
		status_label.text = "Authenticating..."
		await NakamaService.authenticate_device("player_" + str(OS.get_unique_id()))
		
		if not NakamaService.session:
			status_label.text = "Authentication failed"
			return
	
	status_label.text = "Finding match..."
	print("Searching for available matches...")
	
	# Start matchmaking to find or create a match
	await NakamaService.start_matchmaking("*", 2, 4)
	
	if NakamaService.match_id:
		status_label.text = "Match found! Loading..."
		await get_tree().create_timer(0.5).timeout
		get_tree().change_scene_to_file("res://Game.tscn")
	else:
		status_label.text = "No matches found - Try hosting!"


func _on_create_match_back_pressed():
	create_match_panel.visible = false
	main_menu_panel.visible = true
	status_label.text = "Idle"


# Options menu handlers
func _on_music_volume_changed(value: float):
	# TODO: Apply to AudioServer music bus
	AudioServer.set_bus_volume_db(AudioServer.get_bus_index("Music"), linear_to_db(value))
	print("Music volume: ", value)


func _on_sfx_volume_changed(value: float):
	# TODO: Apply to AudioServer SFX bus
	AudioServer.set_bus_volume_db(AudioServer.get_bus_index("SFX"), linear_to_db(value))
	print("SFX volume: ", value)


func _on_resolution_selected(index: int):
	var resolutions = [Vector2i(640, 480), Vector2i(800, 600), Vector2i(1024, 768)]
	get_window().size = resolutions[index]
	print("Resolution changed to: ", resolutions[index])


func _on_fullscreen_toggled(toggled_on: bool):
	if toggled_on:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
	else:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
	print("Fullscreen: ", toggled_on)


func _on_configure_controls_pressed():
	status_label.text = "Control configuration - Coming Soon!"
	print("Control configuration not yet implemented")


func _on_reset_controls_pressed():
	status_label.text = "Controls reset to default"
	print("Reset controls to default")
	await get_tree().create_timer(1.5).timeout
	status_label.text = "Options"


func _on_options_back_pressed():
	options_panel.visible = false
	main_menu_panel.visible = true
	status_label.text = "Idle"
