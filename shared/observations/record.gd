extends RefCounted

var _data: Dictionary = {}
var _properties: Array[Dictionary] = []
var _vectors: Dictionary = {}
var _tile := Vector2i.ZERO

func update(data: Dictionary) -> void:
	_data = data.duplicate(true)
	for key in ["position", "velocity", "kick_direction", "facing"]:
		var value: Array = _data.get(key, [0, 0])
		_vectors[key] = Vector2(float(value[0]), float(value[1]))
	var pos: Vector2 = _vectors.position
	_tile = Vector2i(int(floor(pos.x / GameConfig.TILE_SIZE)), int(floor(pos.y / GameConfig.TILE_SIZE)))
	if _properties.is_empty():
		_properties = _build_properties()

func public_data() -> Dictionary:
	return _data.duplicate(true)

func _get(key: StringName) -> Variant:
	match str(key):
		"position", "velocity", "kick_direction":
			return _vectors.get(str(key), Vector2.ZERO)
		"last_move_direction":
			return _vectors.get("facing", Vector2.DOWN)
		"player_name", "name": return _data.get("username", _data.get("id", ""))
		"bomb_state": return _data.get("state", 0)
		"explosion_range": return _data.get("range", 0)
		"explosion_timer": return _data.get("elapsed", 0.0)
		"has_exploded": return _data.get("exploded", false)
		"kick_speed": return _get("velocity").length()
	return _data.get(str(key))

func public_properties() -> Array[Dictionary]:
	return _properties

func _build_properties() -> Array[Dictionary]:
	var properties: Array[Dictionary] = []
	for key in _data:
		properties.append({"name": key, "type": typeof(_get(key))})
	for key in ["last_move_direction", "player_name", "bomb_state", "explosion_range", "explosion_timer", "has_exploded", "kick_speed"]:
		properties.append({"name": key, "type": typeof(_get(key))})
	return properties

func _get_property_list() -> Array[Dictionary]:
	return public_properties()

func get_tile_position() -> Vector2i:
	return _tile

func get_forecast_observation() -> Dictionary:
	return {"cell": get_tile_position(), "range": _get("explosion_range"), "fuse_lower_bound": _data.fuse_lower_bound, "elapsed": _data.elapsed}

func can_be_picked_up() -> bool:
	return _data.get("state", -1) == ServerBomb.BombState.PLANTED and not _data.get("exploded", false)

func is_ai_bot() -> bool:
	return _data.get("is_bot", false)
