extends Node
## Select regional CJK glyph forms while retaining the original arcade Latin face.
## The shared project Theme propagates updates to existing and future Controls.

const FONT_ROOT := "res://fonts/neptune-arcade/"
const THEME_PATH := "res://themes/main_theme.tres"

var _project_theme: Theme


static func font_path_for_locale(locale: String) -> String:
	var parts := locale.to_lower().replace("-", "_").split("_")
	var language := parts[0] if not parts.is_empty() else ""
	var suffix := ""
	if language == "ja":
		suffix = "_ja"
	elif language == "ko":
		suffix = "_ko"
	elif language == "zh":
		# An explicit script takes precedence over a region's default script.
		if "hans" in parts:
			suffix = "_zh_Hans"
		elif "hk" in parts or "mo" in parts:
			suffix = "_zh_HK"
		elif "hant" in parts or "tw" in parts:
			suffix = "_zh_Hant"
		else:
			suffix = "_zh_Hans"
	return FONT_ROOT + "neptune_arcade" + suffix + ".tres"


func _enter_tree() -> void:
	_project_theme = load(THEME_PATH) as Theme
	refresh()


func _notification(what: int) -> void:
	if what == NOTIFICATION_TRANSLATION_CHANGED and _project_theme != null:
		refresh()


func refresh() -> void:
	if _project_theme == null:
		return
	var font := load(font_path_for_locale(TranslationServer.get_locale())) as Font
	if font != null:
		_project_theme.default_font = font
