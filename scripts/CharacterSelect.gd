extends CanvasLayer

@onready var character_grid = %CharacterGrid
@onready var character_preview_sprite = %CharacterPreviewSprite
@onready var nickname_line_edit = %NicknameLineEdit
@onready var primary_color_picker = %PrimaryColorPicker
@onready var character_name_label = %CharacterNameLabel
@onready var character_bio_text = %CharacterBioText
@onready var back_button = %BackButton

var character_data = {}
var selected_character_name = ""

func _ready():
	if not NakamaService.session:
		back_button.disabled = true
		return

	_load_character_data()
	_populate_roster()
	back_button.pressed.connect(_on_back_button_pressed)

func _load_character_data():
	var dir = DirAccess.open("res://characters")
	if dir:
		dir.list_dir_begin()
		var file_name = dir.get_next()
		while file_name != "":
			if not dir.current_is_dir() and file_name.ends_with(".tscn"):
				var character_name = file_name.get_basename()
				# This is a placeholder. A real implementation would load this from a resource file.
				character_data[character_name] = {
					"name": character_name.capitalize(),
					"description": "A brave bomber with a heart of gold.",
					"scene_path": "res://characters/" + file_name,
					"portrait_idle": "res://characters/portraits/" + character_name.to_lower() + "_idle.png",
					"portrait_hover": "res://characters/portraits/" + character_name.to_lower() + "_hover.png",
					"portrait_pressed": "res://characters/portraits/" + character_name.to_lower() + "_pressed.png",
					"portrait_selected": "res://characters/portraits/" + character_name.to_lower() + "_selected.png",
					"sprite_frames": "res://characters/" + character_name.to_lower() + ".tres"
				}
			file_name = dir.get_next()

func _populate_roster():
	for character_name in character_data:
		var data = character_data[character_name]
		var button = TextureButton.new()
		button.texture_normal = load(data.portrait_idle)
		button.texture_hover = load(data.portrait_hover)
		button.texture_pressed = load(data.portrait_pressed)
		button.texture_focused = load(data.portrait_selected)
		button.custom_minimum_size = Vector2(120, 120)
		button.tooltip_text = data.name
		button.pressed.connect(_on_character_selected.bind(character_name))
		character_grid.add_child(button)

func _on_character_selected(character_name):
	selected_character_name = character_name
	var data = character_data[character_name]

	character_name_label.text = data.name
	character_bio_text.text = data.description

	var frames = load(data.sprite_frames)
	if frames:
		character_preview_sprite.sprite_frames = frames
		character_preview_sprite.play("Idle")

func _on_back_button_pressed():
	var nickname = nickname_line_edit.text
	if nickname.is_empty():
		# You might want to show an error to the user
		return

	var account_update = {
		"display_name": nickname,
		"username": nickname,
		"avatar_url": "",
		"lang_tag": "en",
		"location": "",
		"timezone": "",
		"metadata": {
			"character": selected_character_name,
			"color": primary_color_picker.color.to_html()
		}
	}

	var session = NakamaService.session
	var result = await NakamaService.nakama_client.update_account(session, account_update)

	if result.is_exception():
		print("An error occurred: %s" % result.get_exception().message)
	else:
		print("Account updated successfully")
		get_tree().change_scene_to_file("res://Main.tscn")
