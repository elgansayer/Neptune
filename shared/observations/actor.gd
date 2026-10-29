extends Node2D

var _world: WeakRef
var _port
var _record
var _properties: Array[Dictionary] = []
var _last_result: Dictionary = {}
var _intent := Vector2.ZERO
var _debug_path := PackedVector2Array()
var _debug_target := PackedVector2Array()

var last_command_result: Dictionary:
	get: return _last_result.duplicate(true)
var input_direction: Vector2:
	get: return _intent

func configure(world: Node, port) -> void:
	_world = weakref(world)
	_port = port

func refresh(record) -> void:
	_record = record
	if _properties.is_empty() and record != null:
		for property in record.public_properties():
			if property.name not in ["position", "name"]:
				_properties.append(property)
	if record != null:
		position = record.position

func _get(key: StringName) -> Variant:
	if _record != null:
		return _record.get(key)
	return true if str(key) == "is_dead" else null

func _get_property_list() -> Array[Dictionary]:
	return _properties

func public_data() -> Dictionary:
	return _record.public_data() if _record != null else {}

func _submit(command: Dictionary) -> Dictionary:
	_last_result = _port.invoke(command)
	if _last_result.accepted and command.get("action") == "move":
		_intent = Vector2(float(command.get("x", 0)), float(command.get("y", 0)))
	var world = _world.get_ref()
	if is_instance_valid(world):
		world.refresh()
	return _last_result.duplicate(true)

func set_input(x: Variant, y: Variant) -> Dictionary:
	return _submit({"action": "move", "x": x, "y": y})

func request_bomb_placement() -> Dictionary:
	return _submit({"action": "place_bomb"})

func can_place_bomb() -> bool:
	return _record != null and not _record.is_dead and not _record.placement_disabled and _record.bombs_placed < _record.max_bombs

func get_tile_position() -> Vector2i:
	return Vector2i(int(floor(position.x / GameConfig.TILE_SIZE)), int(floor(position.y / GameConfig.TILE_SIZE)))

func get_bomb_fuse_lower_bound() -> float:
	return float(_record.fuse_lower_bound)

func get_effective_bomb_range() -> int:
	return int(_record.effective_range)

func get_virus_speed_modifier() -> float:
	return float(_record.virus_speed_modifier)

func is_carrying_bomb() -> bool:
	return _record != null and not str(_record.get("carried_bomb_id")).is_empty()

func try_pickup_bomb(bomb: Object) -> bool:
	var world = _world.get_ref()
	if not is_instance_valid(bomb) or not is_instance_valid(world) or world.bombs.get(bomb.get("bomb_id")) != bomb:
		_last_result = {"accepted": false, "reason": "foreign_bomb", "action": "pickup_bomb", "bomb_ids": []}
		return false
	return _submit({"action": "pickup_bomb", "bomb_id": bomb.bomb_id}).accepted

func throw_carried_bomb() -> bool:
	return _submit({"action": "throw_bomb"}).accepted

func trigger_tirra_action() -> Dictionary:
	return _submit({"action": "mount_action"})

func get_observed_contacts() -> Array:
	return _port.contacts()

func set_debug_path(points: PackedVector2Array) -> void:
	_debug_path = points.duplicate()

func set_debug_target_line(points: PackedVector2Array) -> void:
	_debug_target = points.duplicate()
