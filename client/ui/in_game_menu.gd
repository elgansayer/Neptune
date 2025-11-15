extends CanvasLayer
class_name InGameMenu

# In-Game Menu - Non-pausing overlay menu for live gameplay
# Provides access to match status, player list, options, and exit functionality
# Game continues running in the background (server authoritative)

signal menu_closed
signal leave_match_requested

enum MenuPanel {
	MAIN,
	MATCH_STATUS,
	PLAYER_LIST,
	OPTIONS,
	LEAVE_CONFIRM
}

var current_panel = MenuPanel.MAIN
var is_visible = false

# Node references
@onready var main_panel = $MenuContainer/MainMenu
@onready var match_status_panel = $MenuContainer/MatchStatusPanel
@onready var player_list_panel = $MenuContainer/PlayerListPanel
@onready var options_panel = $MenuContainer/OptionsPanel
@onready var leave_confirm_panel = $MenuContainer/LeaveConfirmPanel

# Match Status nodes
@onready var status_timer_label = $MenuContainer/MatchStatusPanel/VBoxContainer/TimerLabel
@onready var status_players_label = $MenuContainer/MatchStatusPanel/VBoxContainer/PlayersLabel
@onready var status_rules_label = $MenuContainer/MatchStatusPanel/VBoxContainer/RulesLabel

# Player List nodes
@onready var player_list_container = $MenuContainer/PlayerListPanel/VBoxContainer/ScrollContainer/PlayerListContainer

func _ready():
	layer = 110  # Above HUD (which is 100)
	hide_menu()
	
	# Connect main menu buttons
	$MenuContainer/MainMenu/VBoxContainer/ResumeButton.pressed.connect(_on_resume_pressed)
	$MenuContainer/MainMenu/VBoxContainer/MatchStatusButton.pressed.connect(_on_match_status_pressed)
	$MenuContainer/MainMenu/VBoxContainer/PlayerListButton.pressed.connect(_on_player_list_pressed)
	$MenuContainer/MainMenu/VBoxContainer/OptionsButton.pressed.connect(_on_options_pressed)
	$MenuContainer/MainMenu/VBoxContainer/LeaveMatchButton.pressed.connect(_on_leave_match_pressed)
	
	# Connect back buttons
	$MenuContainer/MatchStatusPanel/VBoxContainer/BackButton.pressed.connect(_on_back_to_main)
	$MenuContainer/PlayerListPanel/VBoxContainer/BackButton.pressed.connect(_on_back_to_main)
	$MenuContainer/OptionsPanel/VBoxContainer/BackButton.pressed.connect(_on_back_to_main)
	
	# Connect leave confirmation buttons
	$MenuContainer/LeaveConfirmPanel/VBoxContainer/ConfirmButton.pressed.connect(_on_leave_confirmed)
	$MenuContainer/LeaveConfirmPanel/VBoxContainer/CancelButton.pressed.connect(_on_back_to_main)
	
	# Connect audio sliders to update value labels
	var master_slider = $MenuContainer/OptionsPanel/VBoxContainer/MasterVolumeContainer/Slider
	var master_label = $MenuContainer/OptionsPanel/VBoxContainer/MasterVolumeContainer/ValueLabel
	master_slider.value_changed.connect(func(value): master_label.text = "%d%%" % int(value))
	
	var music_slider = $MenuContainer/OptionsPanel/VBoxContainer/MusicVolumeContainer/Slider
	var music_label = $MenuContainer/OptionsPanel/VBoxContainer/MusicVolumeContainer/ValueLabel
	music_slider.value_changed.connect(func(value): music_label.text = "%d%%" % int(value))
	
	var sfx_slider = $MenuContainer/OptionsPanel/VBoxContainer/SFXVolumeContainer/Slider
	var sfx_label = $MenuContainer/OptionsPanel/VBoxContainer/SFXVolumeContainer/ValueLabel
	sfx_slider.value_changed.connect(func(value): sfx_label.text = "%d%%" % int(value))

func _input(event):
	if event.is_action_pressed("ui_cancel"):  # ESC key
		toggle_menu()
		get_viewport().set_input_as_handled()

func toggle_menu():
	if is_visible:
		hide_menu()
	else:
		show_menu()

func show_menu():
	is_visible = true
	visible = true
	show_panel(MenuPanel.MAIN)

func hide_menu():
	is_visible = false
	visible = false
	menu_closed.emit()

func show_panel(panel: MenuPanel):
	current_panel = panel
	
	# Hide all panels
	main_panel.visible = false
	match_status_panel.visible = false
	player_list_panel.visible = false
	options_panel.visible = false
	leave_confirm_panel.visible = false
	
	# Show requested panel
	match panel:
		MenuPanel.MAIN:
			main_panel.visible = true
		MenuPanel.MATCH_STATUS:
			match_status_panel.visible = true
		MenuPanel.PLAYER_LIST:
			player_list_panel.visible = true
		MenuPanel.OPTIONS:
			options_panel.visible = true
		MenuPanel.LEAVE_CONFIRM:
			leave_confirm_panel.visible = true

# Button callbacks
func _on_resume_pressed():
	hide_menu()

func _on_match_status_pressed():
	show_panel(MenuPanel.MATCH_STATUS)

func _on_player_list_pressed():
	show_panel(MenuPanel.PLAYER_LIST)

func _on_options_pressed():
	show_panel(MenuPanel.OPTIONS)

func _on_leave_match_pressed():
	show_panel(MenuPanel.LEAVE_CONFIRM)

func _on_back_to_main():
	show_panel(MenuPanel.MAIN)

func _on_leave_confirmed():
	hide_menu()
	leave_match_requested.emit()

# Public API for updating menu content
func update_match_status(time_remaining: float, alive_count: int, total_count: int, rules: String = "Free For All"):
	"""Update the match status panel with current game state"""
	var minutes = int(time_remaining / 60)
	var seconds = int(time_remaining) % 60
	status_timer_label.text = "Time Remaining: %d:%02d" % [minutes, seconds]
	status_players_label.text = "Players Alive: %d / %d" % [alive_count, total_count]
	status_rules_label.text = "Rules: %s" % rules

func update_player_list(players_data: Dictionary):
	"""Update the player list panel with current players"""
	# Clear existing player entries
	for child in player_list_container.get_children():
		child.queue_free()
	
	# Add player entries
	for peer_id in players_data:
		var player_data = players_data[peer_id]
		var player_entry = create_player_entry(
			player_data.get("username", "Unknown"),
			peer_id,
			player_data.get("is_dead", false)
		)
		player_list_container.add_child(player_entry)

func create_player_entry(username: String, peer_id: String, is_dead: bool) -> HBoxContainer:
	"""Create a single player entry with username and action buttons"""
	var entry = HBoxContainer.new()
	
	# Player name label
	var name_label = Label.new()
	name_label.text = username
	if is_dead:
		name_label.text += " (Dead)"
		name_label.modulate = Color(0.6, 0.6, 0.6)
	name_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	entry.add_child(name_label)
	
	# Mute button
	var mute_button = Button.new()
	mute_button.text = "Mute"
	mute_button.custom_minimum_size = Vector2(80, 30)
	mute_button.pressed.connect(func(): _on_mute_player(peer_id, username))
	entry.add_child(mute_button)
	
	# Report button
	var report_button = Button.new()
	report_button.text = "Report"
	report_button.custom_minimum_size = Vector2(80, 30)
	report_button.pressed.connect(func(): _on_report_player(peer_id, username))
	entry.add_child(report_button)
	
	return entry

func _on_mute_player(peer_id: String, username: String):
	print("[InGameMenu] Mute player requested: ", username, " (", peer_id, ")")
	# TODO: Implement mute functionality

func _on_report_player(peer_id: String, username: String):
	print("[InGameMenu] Report player requested: ", username, " (", peer_id, ")")
	# TODO: Implement report functionality
