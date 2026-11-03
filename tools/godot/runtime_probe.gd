extends Node

const ArenaPack = preload("res://shared/content/arena_pack_loader.gd")
var _content_client: Node
var _content_expected := {}
var _content_case := ""
var _content_mode := "play"
var _content_ready := false
var _content_authenticated := false
var _content_map := false
var _content_snapshot := false
var _content_cancelling := false
var _content_wrong_ready_sent := false
var _content_refusal_seen := false
var _content_finished := false
var _content_receipt := {}
var _content_manifest_hashes := {}

## Test the actual ClientMain/ServerMain transport owners, without login/gameplay.
func _ready() -> void:
	if "--probe-user-data-dir" in OS.get_cmdline_user_args():
		print("NEPTUNE_USER_DATA_DIR=", OS.get_user_data_dir())
		get_tree().quit(0)
		return
	if "--probe-content" in OS.get_cmdline_user_args():
		_start_content_probe()
		return
	var client = get_node("/root/ClientMain")
	var incompatible := "--probe-incompatible" in OS.get_cmdline_user_args()
	if incompatible:
		# Isolated test process only; product configuration stays pinned to [3].
		client.protocol_gate._versions = [4]
		client.pending_initial_map = {"previous_session": true}
	client.connection_succeeded.connect(func():
		if incompatible or client.negotiated_protocol != 3 or client.protocol_gate.selected_version(1) != 3:
			push_error("Runtime probe connected without the supported protocol")
			get_tree().quit(1)
			return
		print("NEPTUNE_PROTOCOL_SELECTED=3")
		client._send_ping()
	)
	client.latency_updated.connect(func(_latency):
		print("NEPTUNE_RUNTIME_CONNECTED")
		get_tree().quit(0)
	)
	client.connection_failed.connect(func():
		if incompatible and client.last_connection_error == "incompatible_protocol_versions" and not client.connected and not client.authenticated and client.negotiated_protocol == 0 and client.pending_initial_map.is_empty():
			print("NEPTUNE_PROTOCOL_CLIENT_REFUSED=incompatible_protocol_versions")
			get_tree().quit(0)
			return
		push_error("Runtime probe could not connect")
		get_tree().quit(1)
	)
	get_tree().create_timer(5.0).timeout.connect(func():
		push_error("Runtime probe connection timeout")
		get_tree().quit(1)
	)
	client.connect_to_server("127.0.0.1")

## This branch uses the production ClientMain download coordinator. Original
## fixtures live only in the separate authority's user directory; a successful
## map is compared with independently hashed bytes from the Python harness.
func _start_content_probe() -> void:
	_content_client = get_node("/root/ClientMain")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--probe-content-expected="):
			_content_expected = JSON.parse_string(arg.trim_prefix("--probe-content-expected="))
		if arg.begins_with("--probe-content-case="):
			_content_case = arg.trim_prefix("--probe-content-case=")
		if arg.begins_with("--probe-content-mode="):
			_content_mode = arg.trim_prefix("--probe-content-mode=")
	if _content_expected.is_empty() or _content_case.is_empty() or _content_mode not in ["play", "cancel", "wrong-ready"]:
		_content_fail("invalid authored probe arguments")
		return
	_content_client.connection_succeeded.connect(func():
		if _content_client.negotiated_protocol != 3:
			_content_fail("content probe connected without protocol 3")
			return
		_content_client.login("Sharing_" + _content_case, "original-fixture-password")
	)
	_content_client.connection_failed.connect(func(): _content_fail("production connection failed"))
	_content_client.content_status_changed.connect(_content_status)
	_content_client.authentication_succeeded.connect(func():
		if not _content_ready or _content_cancelling:
			_content_fail("authenticated before verified content readiness")
			return
		_content_authenticated = true
		_content_check_complete()
	)
	_content_client.authentication_failed.connect(func(reason: String):
		if _content_mode == "wrong-ready" and _content_wrong_ready_sent and reason == "content_lock_mismatch":
			if not _content_refusal_seen:
				_content_refusal_seen = true
				get_tree().create_timer(0.2).timeout.connect(_content_refusal_complete)
		elif _content_mode != "cancel" or not _content_cancelling:
			_content_fail("authentication/content failure: " + reason)
	)
	_content_client.initial_map_received.connect(_content_map_received)
	_content_client.game_state_received.connect(_content_state_received)
	get_tree().create_timer(12.0).timeout.connect(func(): _content_fail("content sharing timeout"))
	_content_client.connect_to_server("127.0.0.1")

func _content_status(receipt: Dictionary) -> void:
	if _content_finished: return
	_content_receipt = receipt.duplicate(true)
	if _content_mode == "wrong-ready" and not _content_wrong_ready_sent and receipt.get("state", "") == "downloading":
		_content_wrong_ready_sent = true
		# Deliberately adversarial test client: the production authority must refuse
		# a claimed readiness for another lock before admitting this participant.
		get_node("/root/ServerMain").rpc_id(1, "content_message", {"type": "ready",
			"session_id": _content_client.content_download.session_id(), "lock_sha256": "0".repeat(64)})
	if _content_mode == "cancel" and not _content_cancelling and receipt.get("received_bytes", 0) > 0:
		_content_cancelling = true
		_content_client.cancel_content_download()
		get_tree().create_timer(0.3).timeout.connect(_content_cancel_complete)
		return
	if receipt.get("state", "") == "ready":
		if _content_cancelling or not receipt.get("accepted", false) or receipt.get("lock_sha256", "") != _content_expected.lock_sha256:
			_content_fail("wrong or cancelled content became ready")
			return
		var paths: Array = receipt.get("manifest_paths", [])
		var loaded := ArenaPack.load_arena(paths, _content_expected.content.content_id, _content_expected.lock)
		if not loaded.accepted or loaded.descriptor != _content_expected.content:
			_content_fail("installed arena did not reproduce the exact independently pinned lock")
			return
		for path in paths:
			var document := ArenaPack._read(path)
			if not document.accepted:
				_content_fail("installed manifest bytes missing")
				return
			var parsed: Dictionary = JSON.parse_string(document.text)
			_content_manifest_hashes[parsed.pack_id] = document.sha256
		for identity in _content_expected.lock.packs:
			if _content_manifest_hashes.get(identity.pack_id, "") != identity.manifest_sha256:
				_content_fail("installed raw manifest digest differs from Python oracle")
				return
		_content_ready = true
	elif not receipt.get("accepted", true) and not _content_cancelling and not (_content_wrong_ready_sent and receipt.get("reason") == "content_lock_mismatch"):
		_content_fail("content coordinator refused: " + str(receipt.get("reason", "unknown")))

func _content_map_received(data: Dictionary) -> void:
	if not _content_ready or _content_cancelling:
		_content_fail("map delivered before verified readiness")
		return
	var config: Dictionary = data.get("map_config", {})
	var packed = data.get("map_packed")
	if not packed is PackedByteArray or data.get("map_width", 0) != _content_expected.width or data.get("map_height", 0) != _content_expected.height:
		_content_fail("downloaded arena dimensions disagree with authority")
		return
	if config.get("lock", {}) != _content_expected.lock or config.get("lock_sha256", "") != _content_expected.lock_sha256 or config.get("content", {}) != _content_expected.content:
		_content_fail("initial map carries stale/wrong content metadata")
		return
	var hashing := HashingContext.new()
	hashing.start(HashingContext.HASH_SHA256)
	hashing.update(packed)
	if hashing.finish().hex_encode() != _content_expected.map_sha256:
		_content_fail("authoritative map geometry differs from installed original arena")
		return
	_content_map = true
	_content_check_complete()

func _content_state_received(state: Dictionary) -> void:
	if not _content_ready or _content_cancelling:
		_content_fail("state delivered before verified readiness")
		return
	if not state.get("a", false): return
	var roster: Dictionary = state.get("p", {})
	var own_id := str(_content_client.multiplayer.get_unique_id())
	if not roster.has(own_id) or roster.size() != 2 or state.get("room", {}).get("occupied", 0) != 2:
		_content_fail("ready client did not reach actual mixed human/bot round")
		return
	_content_snapshot = true
	_content_check_complete()

func _content_check_complete() -> void:
	if _content_finished or not _content_ready or not _content_authenticated or not _content_map or not _content_snapshot: return
	_content_finished = true
	print("NEPTUNE_CONTENT_SHARING=", JSON.stringify({"case": _content_case, "ready": true,
		"authenticated": true, "map": true, "snapshot": true, "cancelled": false, "refused": false,
		"received_bytes": _content_receipt.get("received_bytes", -1), "total_bytes": _content_receipt.get("total_bytes", -1),
		"cache_hits": _content_receipt.get("cache_hits", -1), "pack_count": _content_receipt.get("pack_count", -1),
		"lock_sha256": _content_expected.lock_sha256, "manifest_hashes": _content_manifest_hashes,
		"map_sha256": _content_expected.map_sha256}))
	_content_client.peer.close()
	get_tree().quit(0)

func _content_cancel_complete() -> void:
	if _content_finished: return
	if _content_ready or _content_authenticated or _content_map or _content_snapshot or _content_client.authenticated or not _content_receipt.get("manifest_paths", []).is_empty():
		_content_fail("interrupted download partially enabled content/admission")
		return
	_content_finished = true
	print("NEPTUNE_CONTENT_SHARING=", JSON.stringify({"case": _content_case, "ready": false,
		"authenticated": false, "map": false, "snapshot": false, "cancelled": true, "refused": false,
		"received_bytes": _content_receipt.get("received_bytes", -1), "lock_sha256": _content_expected.lock_sha256}))
	get_tree().quit(0)

func _content_refusal_complete() -> void:
	if _content_finished: return
	if not _content_refusal_seen or _content_ready or _content_authenticated or _content_map or _content_snapshot or _content_client.authenticated or not _content_receipt.get("manifest_paths", []).is_empty():
		_content_fail("wrong-lock readiness partially enabled content/admission")
		return
	_content_finished = true
	print("NEPTUNE_CONTENT_SHARING=", JSON.stringify({"case": _content_case, "ready": false,
		"authenticated": false, "map": false, "snapshot": false, "cancelled": false, "refused": true,
		"reason": "content_lock_mismatch", "received_bytes": _content_receipt.get("received_bytes", -1),
		"lock_sha256": _content_expected.lock_sha256}))
	_content_client.peer.close()
	get_tree().quit(0)

func _content_fail(reason: String) -> void:
	if _content_finished: return
	_content_finished = true
	print("NEPTUNE_CONTENT_SHARING_FAILED=", reason)
	get_tree().quit(1)
