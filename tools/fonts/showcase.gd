extends Control
## Standalone font specimen. Run at 960x720; --screenshot=/absolute/path.png saves then exits.

const PACKAGE := "res://fonts/neptune-arcade/"
const INK := Color("edf3ff")
const GOLD := Color("ffdf61")
const MUTED := Color("89a4c8")


func _ready() -> void:
	get_window().size = Vector2i(960, 720)
	var background := ColorRect.new()
	background.color = Color("081735")
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(background)
	var frame := Panel.new()
	frame.position = Vector2(22, 22)
	frame.size = Vector2(916, 676)
	var style := StyleBoxFlat.new()
	style.bg_color = Color("102449")
	style.border_color = Color("305a91")
	style.set_border_width_all(2)
	frame.add_theme_stylebox_override("panel", style)
	add_child(frame)
	label_at("NEPTUNE ARCADE", Vector2(44, 38), 32, GOLD)
	label_at("Saturn-inspired original pixel face / multilingual Godot stack", Vector2(44, 83), 8, INK)
	label_at("ORIGINAL FACE", Vector2(44, 119), 16, GOLD)
	label_at("ABCDEFGHIJKLMNOPQRSTUVWXYZ", Vector2(44, 149), 24, INK)
	label_at("abcdefghijklmnopqrstuvwxyz  0123456789", Vector2(44, 185), 16, INK)
	label_at("READY!  PLAYER 01  /  SCORE 99999  /  03:00", Vector2(44, 217), 16, GOLD)
	label_at("8px  READY! Player 01", Vector2(44, 252), 8, INK)
	label_at("16px  Prêt! Größe. Tiếng Việt.", Vector2(300, 245), 16, INK)
	label_at("BUNDLED LANGUAGE FALLBACKS", Vector2(44, 285), 16, GOLD)
	var rows := [
		["JAPANESE", "ボンバーマン 日本語 対戦開始", "ja"],
		["SIMPLIFIED CHINESE", "简体中文 开始游戏", "zh_Hans"],
		["TRADITIONAL CHINESE", "繁體中文 開始遊戲", "zh_Hant"],
		["KOREAN", "한국어 게임 시작", "ko"],
		["ARABIC / HEBREW", "ابدأ اللعبة العربية   /   התחל משחק", ""],
		["HINDI / TAMIL", "हिन्दी खेल शुरू करें   /   தமிழ் விளையாட்டு", ""],
		["THAI / BENGALI", "ภาษาไทย เริ่มเกม   /   বাংলা খেলা শুরু", ""],
		["GREEK / CYRILLIC", "Ελληνικά παιχνίδι   /   Начать игру", ""],
	]
	for index in rows.size():
		var row: Array = rows[index]
		var y := 322 + index * 37
		label_at(row[0], Vector2(44, y + 5), 8, MUTED)
		label_at(row[1], Vector2(280, y), 22, INK, row[2])
	label_at("Pixel Latin at 8px multiples. CJK / complex scripts: 16px minimum, 24px recommended.",
		Vector2(44, 637), 8, MUTED)
	label_at("Measured glyph coverage; unsupported Unicode stays visible as missing glyphs.",
		Vector2(44, 656), 8, MUTED)
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--screenshot="):
			capture.call_deferred(argument.trim_prefix("--screenshot="))


func label_at(text: String, position_value: Vector2, size_value: int, color_value: Color,
		region: String = "") -> void:
	var label := Label.new()
	label.text = text
	label.position = position_value
	var suffix := "_" + region if not region.is_empty() else ""
	label.add_theme_font_override("font", load(PACKAGE + "neptune_arcade" + suffix + ".tres"))
	label.add_theme_font_size_override("font_size", size_value)
	label.add_theme_color_override("font_color", color_value)
	add_child(label)


func capture(destination: String) -> void:
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var image := get_viewport().get_texture().get_image()
	if image == null or image.is_empty() or image.save_png(destination) != OK:
		printerr("NEPTUNE_FONT_SCREENSHOT_FAIL")
		get_tree().quit(1)
		return
	print("NEPTUNE_FONT_SCREENSHOT_PASS ", destination)
	get_tree().quit(0)
