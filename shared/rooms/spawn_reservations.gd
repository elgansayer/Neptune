extends RefCounted

## Authority-owned, portable spawn allocation; no gameplay RNG or peer transport.
const FORMAT := "neptune.spawn-reservations/1"
const MAX_CELLS := 65536
const MAX_STARTS := 256
var _cells: Array[Vector2i] = []
var _reserved: Dictionary = {}
var _seed := 0
var _layout_hash := ""

static func failure(reason: String) -> Dictionary:
	return {"accepted": false, "reason": reason}

static func valid_map(map: Array) -> bool:
	if map.is_empty() or not map[0] is Array or map[0].is_empty(): return false
	var width: int = map[0].size()
	if width * map.size() > MAX_CELLS: return false
	for row in map:
		if not row is Array or row.size() != width: return false
		for value in row:
			if not value is int: return false
	return true

static func valid_identity(identity: Variant) -> bool:
	return identity is String and not identity.is_empty() and identity.to_utf8_buffer().size() <= 128

static func open_cell(map: Array, cell: Vector2i) -> bool:
	return cell.y >= 0 and cell.y < map.size() and cell.x >= 0 and cell.x < map[cell.y].size() and map[cell.y][cell.x] == 0

static func supported_start(map: Array, cell: Vector2i) -> bool:
	if not open_cell(map, cell): return false
	for direction in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
		if open_cell(map, cell + direction): return true
	return false

func configure(map: Array, cells: Array[Vector2i], seed_value: int) -> Dictionary:
	if not valid_map(map): return failure("invalid_spawn_map")
	if cells.size() > MAX_STARTS: return failure("spawn_budget_exceeded")
	var distinct := {}
	for cell in cells:
		if cell in distinct: return failure("duplicate_spawn_definition")
		distinct[cell] = true
	var canonical := cells.duplicate()
	canonical.sort_custom(func(a, b): return a.y < b.y or (a.y == b.y and a.x < b.x))
	var portable := []
	for cell in canonical: portable.append([cell.x, cell.y])
	_cells.assign(canonical)
	_seed = seed_value
	_layout_hash = JSON.stringify({"map": map, "starts": portable}).sha256_text()
	_reserved.clear()
	return {"accepted": true, "reason": "configured"}

func reserve(identity: String, map: Array, occupied: Array[Vector2i], requested: Variant = null) -> Dictionary:
	if not valid_identity(identity): return failure("invalid_participant_id")
	if not valid_map(map): return failure("invalid_spawn_map")
	if _reserved.has(identity):
		var existing: Vector2i = _reserved[identity]
		if requested != null and requested != existing: return failure("reservation_mismatch")
		if not supported_start(map, existing) or existing in occupied: return failure("reserved_spawn_unavailable")
		return {"accepted": true, "reason": "reserved", "cell": [existing.x, existing.y], "reused": true}
	var available: Array[Vector2i] = []
	for cell in _cells:
		if cell in _reserved.values() or cell in occupied or not supported_start(map, cell): continue
		available.append(cell)
	if requested != null:
		if requested not in _cells: return failure("undeclared_spawn")
		if requested not in available: return failure("spawn_unavailable")
		available.assign([requested])
	if available.is_empty(): return failure("no_spawn_available")
	# Rendezvous ordering is stable for an identity/seed/layout. Clients receive
	# authority allocations; they never run competing local spawn randomness.
	available.sort_custom(func(a, b): return _score(identity, a) < _score(identity, b))
	var selected: Vector2i = available[0]
	_reserved[identity] = selected
	return {"accepted": true, "reason": "reserved", "cell": [selected.x, selected.y], "reused": false}

func preview(map: Array, occupied: Array[Vector2i]) -> Dictionary:
	if not valid_map(map): return failure("invalid_spawn_map")
	for cell in _cells:
		if cell not in _reserved.values() and cell not in occupied and supported_start(map, cell):
			return {"accepted": true, "reason": "preview", "cell": [cell.x, cell.y]}
	return failure("no_spawn_available")

func _score(identity: String, cell: Vector2i) -> String:
	return ("neptune.spawn/1:%d:%s:%d,%d" % [_seed, identity, cell.x, cell.y]).sha256_text()

func release(identity: String) -> void:
	_reserved.erase(identity)

func snapshot() -> Dictionary:
	var allocations := {}
	for identity in _reserved:
		var cell: Vector2i = _reserved[identity]
		allocations[identity] = [cell.x, cell.y]
	return {"format": FORMAT, "seed": str(_seed), "layout_hash": _layout_hash, "reservations": allocations}

func restore(value: Dictionary, map: Array) -> Dictionary:
	if value.size() != 4 or value.get("format") != FORMAT or value.get("seed") != str(_seed) or value.get("layout_hash") != _layout_hash or not value.get("reservations") is Dictionary:
		return failure("incompatible_spawn_snapshot")
	if value.reservations.size() > _cells.size() or not valid_map(map): return failure("invalid_spawn_snapshot")
	var restored := {}
	var occupied := {}
	for identity in value.reservations:
		var cell_data = value.reservations[identity]
		if not valid_identity(identity) or not cell_data is Array or cell_data.size() != 2:
			return failure("invalid_spawn_snapshot")
		for coordinate in cell_data:
			if typeof(coordinate) not in [TYPE_INT, TYPE_FLOAT] or not is_finite(float(coordinate)) or float(coordinate) != floor(float(coordinate)):
				return failure("invalid_spawn_snapshot")
		if cell_data[0] < 0 or cell_data[1] < 0 or cell_data[0] >= map[0].size() or cell_data[1] >= map.size():
			return failure("invalid_spawn_snapshot")
		var cell := Vector2i(cell_data[0], cell_data[1])
		if cell not in _cells or cell in occupied or not supported_start(map, cell): return failure("invalid_spawn_snapshot")
		occupied[cell] = true
		restored[identity] = cell
	_reserved = restored
	return {"accepted": true, "reason": "restored"}
