extends RefCounted

## One authority-offered data-only room selection. Pulls bounded reliable chunks;
## no paths, URLs, resources or executable payloads are chosen by the peer.
const Manifest = preload("res://shared/content/pack_manifest.gd")
const Locks = preload("res://shared/content/pack_dependency_resolver.gd")
const Archive = preload("res://shared/content/pack_archive.gd")
const Cache = preload("res://shared/content/pack_cache.gd")
const Arena = preload("res://shared/content/arena_pack_loader.gd")
const CHUNK_BYTES := 16384
const MAX_SESSION_BYTES := 32 * 1024 * 1024
const TIMEOUT_MSEC := 30000

signal outbound(message: Dictionary)
signal status_changed(result: Dictionary)

var _cache
var _offer := {}
var _archives: Array = []
var _paths: Array = []
var _index := 0
var _buffer := PackedByteArray()
var _loaded := {}
var _active := false
var _deadline := 0
var _result := {"accepted": false, "state": "idle", "reason": "no_content_offer", "received_bytes": 0,
	"total_bytes": 0, "cache_hits": 0, "pack_count": 0, "lock_sha256": "", "manifest_paths": []}

func _init(cache_root: String = "user://pack-cache") -> void:
	_cache = Cache.new(cache_root)

static func exact_keys(data: Dictionary, keys: Array) -> bool:
	if data.size() != keys.size(): return false
	for key in keys:
		if not data.has(key): return false
	return true

static func validate_offer(message: Dictionary) -> Dictionary:
	if not exact_keys(message, ["type", "session_id", "lock", "lock_sha256", "content_id", "archives"]) or message.type != "offer":
		return Manifest.failure("invalid_content_offer", "offer")
	if not Manifest.valid_hash(message.session_id) or not Manifest.valid_id(message.content_id) or not Manifest.valid_hash(message.lock_sha256):
		return Manifest.failure("invalid_content_offer", "offer.identity")
	var checked := Locks.validate_lock(message.lock)
	if not checked.accepted or checked.get("lock_sha256", "") != message.lock_sha256:
		return Manifest.failure("content_lock_hash_mismatch", "offer.lock")
	if not message.archives is Array or message.archives.size() != checked.lock.packs.size():
		return Manifest.failure("invalid_content_archives", "offer.archives")
	var total := 0
	var seen := {}
	for index in message.archives.size():
		var item = message.archives[index]
		if not item is Dictionary or not exact_keys(item, ["identity", "sha256", "size_bytes"]):
			return Manifest.failure("invalid_content_archive", "offer.archives")
		if item.identity != checked.lock.packs[index] or not Manifest.valid_hash(item.sha256) or seen.has(item.sha256):
			return Manifest.failure("invalid_content_archive_identity", "offer.archives")
		if not item.size_bytes is int or item.size_bytes <= 0 or item.size_bytes > Archive.MAX_ARCHIVE_BYTES:
			return Manifest.failure("content_archive_byte_budget_exceeded", "offer.archives")
		seen[item.sha256] = true
		total += item.size_bytes
		if total > MAX_SESSION_BYTES:
			return Manifest.failure("content_session_byte_budget_exceeded", "offer.archives")
	return {"accepted": true, "total_bytes": total}

func begin(message: Dictionary) -> Dictionary:
	if _active:
		_fail("unexpected_content_offer")
		return receipt()
	var checked := validate_offer(message)
	if not checked.accepted:
		_fail(checked.reason)
		return receipt()
	_offer = message.duplicate(true)
	_archives = message.archives.duplicate(true)
	_paths = []
	_index = 0
	_buffer = PackedByteArray()
	_loaded = {}
	_active = true
	_deadline = Time.get_ticks_msec() + TIMEOUT_MSEC
	_result = {"accepted": true, "state": "downloading", "reason": "content_offered", "received_bytes": 0,
		"total_bytes": checked.total_bytes, "cache_hits": 0, "pack_count": _archives.size(),
		"lock_sha256": message.lock_sha256, "manifest_paths": []}
	_publish()
	if _active: _advance()
	return receipt()

func receive(message: Dictionary) -> Dictionary:
	if not _active: return receipt()
	if not exact_keys(message, ["type", "session_id", "sha256", "offset", "data"]) or message.type != "chunk":
		_fail("invalid_content_chunk")
		return receipt()
	if message.session_id != _offer.session_id or _index >= _archives.size():
		_fail("stale_content_chunk")
		return receipt()
	var item: Dictionary = _archives[_index]
	if message.sha256 != item.sha256 or not message.offset is int or message.offset != _buffer.size():
		_fail("unexpected_content_chunk_offset")
		return receipt()
	var expected := mini(CHUNK_BYTES, int(item.size_bytes) - _buffer.size())
	if not message.data is PackedByteArray or message.data.size() != expected or expected <= 0:
		_fail("content_chunk_byte_budget_exceeded")
		return receipt()
	_buffer.append_array(message.data)
	_result.received_bytes += message.data.size()
	_result.reason = "content_downloading"
	_publish()
	# A synchronous progress listener can cancel even at the final chunk boundary.
	if _active: _advance()
	return receipt()

func _advance() -> void:
	while _active and _index < _archives.size():
		var item: Dictionary = _archives[_index]
		if _buffer.is_empty():
			var cached: Dictionary = _cache.lookup(item.identity, item.sha256)
			if cached.accepted:
				_paths.append(cached.manifest_path)
				_result.cache_hits += 1
				_index += 1
				_result.reason = "content_cache_hit"
				_publish()
				continue
		if _buffer.size() == item.size_bytes:
			var installed: Dictionary = _cache.install(_buffer, item.sha256, item.identity)
			if not installed.accepted:
				_fail("content_install_refused:" + str(installed.reason))
				return
			_paths.append(installed.manifest_path)
			_index += 1
			_buffer = PackedByteArray()
			continue
		outbound.emit({"type": "request", "session_id": _offer.session_id, "sha256": item.sha256, "offset": _buffer.size()})
		return
	if not _active: return
	var loaded := Arena.load_arena(_paths, _offer.content_id, _offer.lock)
	if not loaded.accepted or loaded.get("lock_sha256", "") != _offer.lock_sha256:
		_fail("content_runtime_refused:" + str(loaded.get("reason", "content_lock_mismatch")))
		return
	_loaded = loaded
	_result.state = "ready"
	_result.reason = "content_verified"
	_result.manifest_paths = _paths.duplicate()
	_publish()
	if not _active: return
	_active = false
	outbound.emit({"type": "ready", "session_id": _offer.session_id, "lock_sha256": _offer.lock_sha256})

func tick() -> void:
	if _active and Time.get_ticks_msec() >= _deadline: _fail("content_download_timeout")

func cancel(reason: String = "content_cancelled") -> void:
	if _offer.is_empty():
		_active = false
		return
	_fail(reason)

func _fail(reason: String) -> void:
	var send_cancel := _active
	var cancelled_session: String = _offer.get("session_id", "")
	_active = false
	_buffer = PackedByteArray()
	_result.accepted = false
	_result.state = "failed"
	_result.reason = reason
	_result.manifest_paths = []
	_publish()
	if send_cancel:
		outbound.emit({"type": "cancel", "session_id": cancelled_session})

func _publish() -> void:
	status_changed.emit(receipt())

func receipt() -> Dictionary:
	return _result.duplicate(true)

func session_id() -> String:
	return _offer.get("session_id", "")

func validate_initial_map(data: Dictionary) -> Dictionary:
	if _result.state != "ready" or _loaded.is_empty():
		return Manifest.failure("content_map_before_ready", "map_config.lock")
	var config = data.get("map_config")
	if not config is Dictionary or config.get("lock") != _offer.lock or config.get("lock_sha256") != _offer.lock_sha256:
		return Manifest.failure("content_map_lock_mismatch", "map_config.lock")
	if config.get("content") != _loaded.descriptor or config.get("selection") != _loaded.selection:
		return Manifest.failure("content_map_selection_mismatch", "map_config.content")
	var map: Dictionary = _loaded.map
	if data.get("map_width") != map.width or data.get("map_height") != map.height or config.get("width") != map.width or config.get("height") != map.height or config.get("tile_size") != map.tile_size or config.get("name") != map.name or config.get("render_geometry") != true:
		return Manifest.failure("content_map_geometry_mismatch", "map_config")
	var packed = data.get("map_packed")
	if not packed is PackedByteArray or packed.size() != map.width * map.height:
		return Manifest.failure("content_map_byte_budget_exceeded", "map_packed")
	# Terrain can differ from the definition when joining a live round after blocks
	# were destroyed. The authority remains responsible for those simulation changes.
	for cell in packed:
		if cell > 2: return Manifest.failure("content_map_invalid_terrain", "map_packed")
	return {"accepted": true, "reason": "content_map_verified"}
