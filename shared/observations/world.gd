extends Node

const Record = preload("res://shared/observations/record.gd")
const Queries = preload("res://shared/observations/queries.gd")
const Actor = preload("res://shared/observations/actor.gd")
var _source
var _frame: Dictionary = {}
var _version := -1
var _terrain: Array = []
var _dimensions := Vector2i.ONE
var _models := {"players": {}, "bombs": {}, "powerups": {}}
var own_actor: Node2D
var own_peer_id := 0
var ai_manager

func _init(source) -> void:
	_source = source
	refresh()

func configure_actor(peer_id: int, port) -> void:
	own_peer_id = peer_id
	own_actor = Actor.new()
	own_actor.name = "ObservedActor_%d" % abs(peer_id)
	own_actor.configure(self, port)
	add_child(own_actor)
	own_actor.refresh(_models.players.get(peer_id))

func refresh(force: bool = false) -> void:
	_source.ensure(force)
	_sync()

func _sync() -> void:
	if _source.dirty:
		_source.ensure_dirty()
	if _version == _source.version:
		return
	_frame = _source.frame()
	_version = _source.version
	_terrain = _frame.get("terrain", [])
	_dimensions = Vector2i(_terrain[0].size(), _terrain.size()) if not _terrain.is_empty() else Vector2i.ZERO
	for group in _models:
		var live := {}
		for id in _frame.get(group, {}):
			var key = int(id) if group == "players" else id
			var record = _models[group].get(key)
			if record == null:
				record = Record.new()
			record.update(_frame[group][id])
			live[key] = record
		_models[group] = live
	if is_instance_valid(own_actor):
		own_actor.refresh(_models.players.get(own_peer_id))

func _get(key: StringName) -> Variant:
	_sync()
	match str(key):
		"game_map": return _frame.get("terrain", [[1]]).duplicate(true)
		"players", "bombs", "powerups": return _models[str(key)].duplicate()
		"active_explosion_tiles": return _frame.get("flames", {}).duplicate(true)
		"current_time_msec": return float(_frame.get("server_time", 0.0))
		"simulation_tick": return int(_frame.get("tick", 0))
		"match_active": return _frame.get("active", false)
		"bot_supported": return _frame.get("valid", false) and _frame.get("bot_supported", false)
	return null

func _get_property_list() -> Array[Dictionary]:
	return [{"name": "game_map", "type": TYPE_ARRAY}, {"name": "players", "type": TYPE_DICTIONARY}, {"name": "bombs", "type": TYPE_DICTIONARY}, {"name": "powerups", "type": TYPE_DICTIONARY}, {"name": "active_explosion_tiles", "type": TYPE_DICTIONARY}, {"name": "current_time_msec", "type": TYPE_FLOAT}, {"name": "simulation_tick", "type": TYPE_INT}, {"name": "match_active", "type": TYPE_BOOL}, {"name": "bot_supported", "type": TYPE_BOOL}]

func public_snapshot() -> Dictionary:
	refresh()
	return _frame.duplicate(true)

func get_tile_type(tile: Vector2i) -> int:
	if _source.dirty or _version != _source.version:
		_sync()
	if tile.x < 0 or tile.y < 0 or tile.x >= _dimensions.x or tile.y >= _dimensions.y:
		return 1
	return int(_terrain[tile.y][tile.x])

func get_map_dimensions() -> Vector2i:
	if _source.dirty or _version != _source.version:
		_sync()
	return _dimensions

func get_simulation_time_msec() -> float:
	# Clock queries are observation boundaries even in controlled/frozen experiments.
	refresh()
	return float(_frame.get("server_time", 0.0))

func get_simulation_time_sec() -> float:
	return get_simulation_time_msec() / 1000.0

func occupants(tile: Vector2i, peer_id: int = 0) -> Array[Dictionary]:
	refresh()
	return Queries.at_cell(_frame, tile, peer_id)

func place_bomb(player) -> Dictionary:
	if player != own_actor or not is_instance_valid(own_actor):
		return {"accepted": false, "reason": "foreign_player", "action": "place_bomb", "bomb_ids": []}
	return own_actor.request_bomb_placement()
