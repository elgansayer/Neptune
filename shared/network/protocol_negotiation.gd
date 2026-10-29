extends Node

## Gameplay compatibility, not account authentication or a pack/content lock.
## SceneMultiplayer withholds RPCs and peer_connected until both sides complete.
const FORMAT := "neptune.protocol/1"
const SUPPORTED_VERSIONS := [1]
const MAX_OFFER_BYTES := 1024
const MAX_VERSIONS := 8
const MAX_VERSION := 65535
const HANDSHAKE_TIMEOUT := 3.0

signal rejected(peer_id: int, reason: String)

var _api: SceneMultiplayer
var _versions: Array = []
var _selected := {}
var _failed := {}

static func validate_versions(value: Variant) -> bool:
	if not value is Array or value.is_empty() or value.size() > MAX_VERSIONS:
		return false
	var seen := {}
	for version in value:
		if not (version is int or version is float): return false
		if not is_finite(float(version)) or version < 1 or version > MAX_VERSION or floor(float(version)) != float(version): return false
		if seen.has(int(version)): return false
		seen[int(version)] = true
	return true

static func evaluate_offer(data: PackedByteArray, supported: Array = SUPPORTED_VERSIONS) -> Dictionary:
	if data.size() > MAX_OFFER_BYTES:
		return {"accepted": false, "reason": "protocol_offer_too_large"}
	if not validate_versions(supported):
		return {"accepted": false, "reason": "invalid_local_protocol_versions"}
	# The bootstrap grammar needs ASCII only. Reject non-ASCII before UTF-8
	# decoding so malformed bytes cannot produce an engine decode error.
	for byte in data:
		if byte > 127:
			return {"accepted": false, "reason": "invalid_protocol_offer"}
	var parser := JSON.new()
	if parser.parse(data.get_string_from_utf8()) != OK:
		return {"accepted": false, "reason": "invalid_protocol_offer"}
	var offer = parser.data
	if not offer is Dictionary or offer.size() != 2 or not offer.get("format") is String:
		return {"accepted": false, "reason": "invalid_protocol_offer"}
	if offer.format != FORMAT or not validate_versions(offer.get("versions")):
		return {"accepted": false, "reason": "invalid_protocol_offer"}
	var selected := 0
	for version in offer.versions:
		if int(version) in supported:
			selected = maxi(selected, int(version))
	if selected == 0:
		return {"accepted": false, "reason": "incompatible_protocol_versions"}
	return {"accepted": true, "reason": "compatible", "version": selected}

func configure(api: SceneMultiplayer, supported: Array = SUPPORTED_VERSIONS) -> Error:
	if api == null or _api != null or api.auth_callback.is_valid() or not validate_versions(supported):
		return ERR_INVALID_PARAMETER
	_api = api
	_versions = supported.duplicate()
	_api.allow_object_decoding = false
	_api.auth_timeout = HANDSHAKE_TIMEOUT
	_api.auth_callback = _receive_offer
	_api.peer_authenticating.connect(_begin)
	_api.peer_authentication_failed.connect(_authentication_failed)
	_api.peer_disconnected.connect(_forget)
	return OK

func selected_version(peer_id: int) -> int:
	return _selected.get(peer_id, 0)

func _begin(peer_id: int) -> void:
	_forget(peer_id)
	var data := JSON.stringify({"format": FORMAT, "versions": _versions}).to_utf8_buffer()
	if _api.send_auth(peer_id, data) != OK:
		_reject(peer_id, "protocol_offer_send_failed")

func _receive_offer(peer_id: int, data: PackedByteArray) -> void:
	if peer_id not in _api.get_authenticating_peers() or _selected.has(peer_id) or _failed.has(peer_id):
		return
	var result := evaluate_offer(data, _versions)
	if not result.accepted:
		_reject(peer_id, result.reason)
		return
	_selected[peer_id] = result.version
	if _api.complete_auth(peer_id) != OK:
		_reject(peer_id, "protocol_completion_failed")

func _reject(peer_id: int, reason: String) -> void:
	_selected.erase(peer_id)
	_failed[peer_id] = true
	rejected.emit(peer_id, reason)
	# Never complete this peer. Keep the already-sent reliable offer deliverable
	# so both clients can explain incompatibility instead of racing an immediate
	# disconnect against it. auth_timeout bounds the pending slot to three seconds;
	# a disconnect/timeout clears this record via peer_authentication_failed.

func _authentication_failed(peer_id: int) -> void:
	if not _failed.has(peer_id):
		rejected.emit(peer_id, "protocol_handshake_timeout_or_disconnect")
	_forget(peer_id)

func _forget(peer_id: int) -> void:
	_selected.erase(peer_id)
	_failed.erase(peer_id)
