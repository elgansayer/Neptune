extends RefCounted

const Capture = preload("res://shared/observations/public_snapshot.gd")
var _authority: WeakRef
var _frame: Dictionary = {}
var version := 0
var dirty := true
var last_capture_usec := 0
var max_capture_usec := 0

func _init(authority: Node) -> void:
	_authority = weakref(authority)

func mark_dirty(_node: Node = null) -> void:
	dirty = true

func ensure(force: bool = false) -> void:
	var game = _authority.get_ref()
	if not is_instance_valid(game):
		return
	if force or dirty or _frame.get("tick", -1) != game.simulation_tick or _frame.get("server_time", -1.0) != game.get_simulation_time_msec():
		var start := Time.get_ticks_usec()
		_frame = Capture.capture(game)
		last_capture_usec = Time.get_ticks_usec() - start
		max_capture_usec = maxi(max_capture_usec, last_capture_usec)
		dirty = false
		version += 1

func ensure_dirty() -> void:
	if dirty:
		ensure()

func export_snapshot(force: bool = false) -> Dictionary:
	ensure(force)
	return _frame.duplicate(true)

func frame() -> Dictionary:
	ensure()
	return _frame # Internal only; public exports always copy.
