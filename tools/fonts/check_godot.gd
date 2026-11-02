extends SceneTree
## Exercise the actual imported font stack and Godot's HarfBuzz text shaping.

const PACKAGE := "res://fonts/neptune-arcade/"
const REGIONS := {
	"ja": ["ja", 0],
	"zh_Hans": ["zh_CN", 2],
	"zh_Hant": ["zh_TW", 3],
	"zh_HK": ["zh_HK", 4],
	"ko": ["ko", 1],
}
const SAMPLES := {
	"en": "READY! Player 123",
	"fr": "Prêt à jouer! Ça commence.",
	"de": "Größe und Spaß",
	"el": "Ξεκινήστε το παιχνίδι",
	"ru": "Начать игру",
	"ja": "ボンバーマン 日本語 対戦開始",
	"zh_CN": "简体中文 开始游戏",
	"zh_TW": "繁體中文 開始遊戲",
	"ko": "한국어 게임 시작",
	"ar": "ابدأ اللعبة العربية",
	"he": "התחל משחק בעברית",
	"hi": "हिन्दी खेल शुरू करें",
	"bn": "বাংলা খেলা শুরু",
	"ta": "தமிழ் விளையாட்டு",
	"te": "తెలుగు ఆట",
	"th": "ภาษาไทย เริ่มเกม",
	"vi": "Tiếng Việt bắt đầu",
	"ka": "ქართული თამაში",
	"hy": "Հայերեն խաղ",
	"am": "አማርኛ ጨዋታ",
}

var failures: Array[String] = []
var checks := 0
var text_server := TextServerManager.get_primary_interface()


func _initialize() -> void:
	call_deferred("_run")


func require(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures.append(message)
		printerr("FAIL: ", message)


func collect_files(font: Font, seen: Dictionary) -> void:
	if font == null or seen.has(font.get_instance_id()):
		return
	seen[font.get_instance_id()] = font
	if font is FontFile:
		require(not font.allow_system_fallback, "System font fallback enabled: " + font.resource_path)
	elif font is FontVariation:
		collect_files(font.base_font, seen)
	else:
		require(false, "Unexpected platform-dependent font resource: " + font.get_class())
	for fallback in font.fallbacks:
		collect_files(fallback, seen)


func shape(text: String, font: Font, language: String) -> Array[Dictionary]:
	var line := TextLine.new()
	require(line.add_string(text, font, 24, language), "Could not add text for " + language)
	require(line.get_line_width() > 0, "Empty shaped width for " + language)
	return text_server.shaped_text_get_glyphs(line.get_rid())


func has_curved_outline(font: FontFile, character: String) -> bool:
	var rid: RID = font.get_rids()[0]
	var glyph := text_server.font_get_glyph_index(rid, 32, character.unicode_at(0), 0)
	var contours := text_server.font_get_glyph_contours(rid, 32, glyph)
	for point in contours.get("points", []):
		if point.z == 0.0:
			return true
	return false


func glyphs_are_present(glyphs: Array[Dictionary], language: String) -> bool:
	var present := not glyphs.is_empty()
	for glyph in glyphs:
		# Godot inserts virtual break opportunities between CJK characters; these
		# have glyph index zero. Cluster continuations have count=0 and no VALID
		# flag, even when their combining glyph is present. Check real glyph RIDs
		# and indices instead of mistaking either representation for missing text.
		if glyph.flags & TextServer.GRAPHEME_IS_VIRTUAL:
			continue
		if not glyph.font_rid.is_valid() or glyph.index == 0:
			present = false
			printerr("Missing glyph in ", language, ": ", glyph)
	require(present, "Missing glyphs after real shaping for " + language)
	return present


func font_for_language(language: String, default_font: Font) -> Font:
	var suffix := ""
	if language == "ja":
		suffix = "ja"
	elif language in ["zh_CN", "zh_Hans"]:
		suffix = "zh_Hans"
	elif language in ["zh_TW", "zh_Hant"]:
		suffix = "zh_Hant"
	elif language == "zh_HK":
		suffix = "zh_HK"
	elif language == "ko":
		suffix = "ko"
	if suffix.is_empty():
		return default_font
	return load(PACKAGE + "neptune_arcade_" + suffix + ".tres") as Font


func check_locale_switcher() -> void:
	var locale_script = load("res://scripts/arcade_font_locale.gd")
	if locale_script == null:
		require(false, "Missing game locale switcher")
		return
	var expected := {
		"ja_JP": "ja", "zh_CN": "zh_Hans", "zh_SG": "zh_Hans",
		"zh-Hans": "zh_Hans", "zh_TW": "zh_Hant", "zh-Hant": "zh_Hant",
		"zh_HK": "zh_HK", "ko_KR": "ko",
	}
	for locale in expected:
		var suffix: String = expected[locale]
		require(locale_script.font_path_for_locale(locale) == PACKAGE + "neptune_arcade_" + suffix + ".tres",
			"Incorrect regional font mapping for " + locale)
	var switcher: Node = locale_script.new()
	root.add_child(switcher)
	var old_locale := TranslationServer.get_locale()
	for locale in ["ja", "zh_CN", "zh_TW", "zh_HK", "ko"]:
		TranslationServer.set_locale(locale)
		switcher.refresh()
		var theme := load("res://themes/main_theme.tres") as Theme
		require(theme.default_font.resource_path == locale_script.font_path_for_locale(locale),
			"Theme did not switch for locale " + locale)
	TranslationServer.set_locale(old_locale)
	switcher.refresh()
	switcher.free()


func _run() -> void:
	require(text_server.has_feature(TextServer.FEATURE_SHAPING), "Advanced script shaping is unavailable")
	var font := load(PACKAGE + "neptune_arcade.tres") as FontVariation
	if font == null:
		require(false, "Default font resource failed to load")
		finish()
		return
	var all_resources := {}
	collect_files(font, all_resources)
	require(all_resources.size() > 20, "Bundled multilingual fallback chain is incomplete")
	var primary := font.base_font as FontFile
	require(primary != null, "Primary bubble face must be a bundled FontFile")
	if primary != null:
		require(primary.resource_path.ends_with("/NeptuneBubble.ttf"),
			"The default display font must use Neptune Bubble")
		require(primary.antialiasing == TextServer.FONT_ANTIALIASING_GRAY,
			"The bubble font needs smooth grayscale antialiasing")
		require(has_curved_outline(primary, "O"),
			"The bubble face needs real curved glyph outlines")
		for codepoint in range(32, 127):
			require(primary.has_char(codepoint), "Primary face is missing ASCII U+%04X" % codepoint)
		var glyphs := shape("BOMBERMAN abc 0123!?", font, "en")
		glyphs_are_present(glyphs, "primary ASCII")
		var primary_rids := primary.get_rids()
		for glyph in glyphs:
			require(glyph.font_rid in primary_rids, "ASCII selected a fallback instead of original bubble face")
	var pixel := load(PACKAGE + "neptune_pixel.tres") as FontVariation
	require(pixel != null, "Optional pixel font resource failed to load")
	if pixel != null:
		var pixel_primary := pixel.base_font as FontFile
		require(pixel_primary != null, "Optional pixel font is missing its bundled primary face")
		if pixel_primary != null:
			require(pixel_primary.resource_path.ends_with("/NeptuneArcade.ttf"),
				"The optional pixel resource must preserve Neptune Arcade")
			require(pixel_primary.antialiasing == TextServer.FONT_ANTIALIASING_NONE,
				"The optional pixel font must preserve crisp unfiltered edges")
			require(not has_curved_outline(pixel_primary, "O"),
				"The optional pixel face must preserve its original grid outlines")
			for codepoint in range(32, 127):
				require(pixel_primary.has_char(codepoint), "Pixel face is missing ASCII U+%04X" % codepoint)
			glyphs_are_present(shape("PIXEL HUD Player 01", pixel, "en"), "optional pixel ASCII")
	for suffix in REGIONS:
		var locale_data: Array = REGIONS[suffix]
		var regional := load(PACKAGE + "neptune_arcade_" + suffix + ".tres") as FontVariation
		require(regional != null, "Regional resource failed to load: " + suffix)
		if regional == null:
			continue
		collect_files(regional, all_resources)
		var glyphs := shape("骨", regional, locale_data[0])
		if glyphs_are_present(glyphs, suffix):
			for glyph in glyphs:
				require(text_server.font_get_face_index(glyph.font_rid) == locale_data[1],
					"Wrong CJK collection face selected at runtime for " + suffix)
	for language in SAMPLES:
		var sample_font := font_for_language(language, font)
		if sample_font != null:
			glyphs_are_present(shape(SAMPLES[language], sample_font, language), language)
		else:
			require(false, "Missing sample font for " + language)
	var sample_data = JSON.parse_string(FileAccess.get_file_as_string(PACKAGE + "sample-texts.json"))
	require(sample_data is Dictionary and sample_data.get("samples", []).size() >= 40,
		"Declared language sample fixture is missing or unexpectedly empty")
	if sample_data is Dictionary:
		for sample in sample_data.get("samples", []):
			var locale: String = sample.locale
			var sample_font := font_for_language(locale, font)
			glyphs_are_present(shape(sample.text, sample_font, locale), "declared sample " + locale)
	var arabic := shape("سلام", font, "ar")
	if glyphs_are_present(arabic, "Arabic joining"):
		require(arabic.size() < 4, "Arabic lam-alef ligature was not formed")
		require(arabic.front().start > arabic.back().start, "Arabic glyph run did not reorder right to left")
	var devanagari := shape("क्षि", font, "hi")
	if glyphs_are_present(devanagari, "Devanagari conjunct"):
		var conjunct := false
		for glyph in devanagari:
			conjunct = conjunct or glyph.end - glyph.start > 1
		require(conjunct, "Devanagari shaping did not form a multi-character cluster")
	# A private-use character is deliberately unsupported. It must remain missing;
	# inventing glyph aliases or relying on machine-installed fonts would conceal this.
	var unknown := shape(String.chr(0xF0000), font, "en")
	var missing_detected := false
	for glyph in unknown:
		missing_detected = missing_detected or not glyph.font_rid.is_valid()
	require(missing_detected, "Unknown-codepoint negative control did not stay unsupported")
	check_locale_switcher()
	finish()


func finish() -> void:
	if failures.is_empty():
		print("NEPTUNE_FONT_CHECK_PASS ", checks, " assertions; shaping, CJK faces, locale switching and negative control")
		quit(0)
	else:
		printerr("NEPTUNE_FONT_CHECK_FAIL ", failures.size(), " failures / ", checks, " assertions")
		quit(1)
