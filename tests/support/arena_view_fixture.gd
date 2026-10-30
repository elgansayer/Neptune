extends "res://client/game_view.gd"

## Keep production map rendering/framing/HUD; omit network/debug/global layers.
func _ready() -> void:
	camera.enabled = true
	camera.anchor_mode = Camera2D.ANCHOR_MODE_DRAG_CENTER
	hud = load("res://client/ui/game_hud.tscn").instantiate()
	add_child(hud)
	_connect_arena_framing()
	set_physics_process(false)
