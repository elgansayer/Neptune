extends "res://tests/bot_test_suite.gd"

const Protocol = preload("res://shared/network/protocol_negotiation.gd")

# These parser/configuration cases need the actual GDScript runtime, no actors.
# Network integration is separately required by check_runtime.py.
func setup_suite() -> void: pass
func teardown_suite() -> void: pass
func setup_test() -> void: pass
func teardown_test() -> void: pass

func _offer(versions: Variant, format: Variant = Protocol.FORMAT) -> PackedByteArray:
	return JSON.stringify({"format": format, "versions": versions}).to_utf8_buffer()

func test_current_protocol_is_explicit() -> Variant:
	return assert_eq(Protocol.evaluate_offer(_offer([1])), {"accepted": true, "reason": "compatible", "version": 1}, "Current gameplay protocol must be selected explicitly")

func test_highest_shared_version_is_symmetric_and_order_independent() -> Variant:
	for pair in [[[1, 2, 3], [2, 1]], [[3, 1, 2], [1, 2]], [[2, 1], [3, 2, 1]]]:
		var result: Dictionary = Protocol.evaluate_offer(_offer(pair[0]), pair[1])
		if not result.accepted or result.version != 2: return "Intersection selection disagreed or depended on declaration order"
	return true

func test_no_common_protocol_has_no_fallback() -> Variant:
	var result: Dictionary = Protocol.evaluate_offer(_offer([2]))
	return assert_true(not result.accepted and result.reason == "incompatible_protocol_versions" and not result.has("version"), "Future-only peers cannot fall back silently")

func test_empty_missing_or_unknown_envelope_is_rejected() -> Variant:
	for raw in ["", "{}", "[]", "null", "true", "1", "\"text\"", "not JSON", "{\"versions\":[1]}", "{\"format\":\"neptune.protocol/1\"}"]:
		if Protocol.evaluate_offer(raw.to_utf8_buffer()).accepted: return "Malformed/missing bootstrap envelope accepted"
	return true

func test_unknown_format_and_extra_fields_are_rejected() -> Variant:
	for value in [null, 1, true, "neptune.protocol/0", "neptune.protocol/2", ""]:
		if Protocol.evaluate_offer(_offer([1], value)).accepted: return "Unknown bootstrap format accepted"
	var extra := {"format": Protocol.FORMAT, "versions": [1], "fallback": true}
	return assert_true(not Protocol.evaluate_offer(JSON.stringify(extra).to_utf8_buffer()).accepted, "Unknown capabilities cannot be ignored in bootstrap")

func test_trailing_documents_cannot_hide_behind_a_valid_offer() -> Variant:
	var raw := _offer([1]).get_string_from_utf8()
	for suffix in ["true", raw, "{}", " trailing text"]:
		if Protocol.evaluate_offer((raw + suffix).to_utf8_buffer()).accepted:
			return "A valid prefix hid trailing non-whitespace bytes"
	return true

func test_invalid_version_types_and_bounds_are_rejected() -> Variant:
	for value in [null, true, false, "1", -1, 0, 1.5, NAN, INF, 65536, 4294967297, {}, []]:
		if Protocol.validate_versions([value]): return "Invalid protocol version type/range accepted"
		if Protocol.evaluate_offer(_offer([value])).accepted: return "Invalid remote protocol version selected"
	return true

func test_duplicate_or_unbounded_version_lists_are_rejected() -> Variant:
	for value in [[], [1, 1], [1, 1.0], [1, 2, 3, 4, 5, 6, 7, 8, 9], "1", {}, null]:
		if Protocol.validate_versions(value) or Protocol.evaluate_offer(_offer(value)).accepted:
			return "Invalid/duplicated/unbounded version set accepted"
	return true

func test_supported_version_count_and_numeric_boundaries() -> Variant:
	var versions := [1, 2, 3, 4, 5, 6, 7, 65535]
	var result: Dictionary = Protocol.evaluate_offer(_offer(versions), [65535])
	return assert_true(result.accepted and result.version == 65535 and Protocol.validate_versions(versions), "Documented version/count boundaries must work")

func test_offer_byte_budget_includes_whitespace() -> Variant:
	var raw := _offer([1]).get_string_from_utf8()
	var boundary := (raw + " ".repeat(Protocol.MAX_OFFER_BYTES - raw.length())).to_utf8_buffer()
	var overflow := boundary.duplicate()
	overflow.append(32)
	return assert_true(Protocol.evaluate_offer(boundary).accepted and Protocol.evaluate_offer(overflow).reason == "protocol_offer_too_large", "Limits cover the received byte packet before parsing")

func test_non_ascii_and_invalid_utf8_are_rejected_without_engine_errors() -> Variant:
	for data in [PackedByteArray([255, 254]), "日本語".to_utf8_buffer(), PackedByteArray([123, 34, 128])]:
		if Protocol.evaluate_offer(data).accepted: return "Non-bootstrap byte sequence accepted"
	return true

func test_invalid_local_support_cannot_accept_a_remote_peer() -> Variant:
	for versions in [[], [true], [0], [1, 1]]:
		var result: Dictionary = Protocol.evaluate_offer(_offer([1]), versions)
		if result.accepted or result.reason != "invalid_local_protocol_versions": return "Invalid local configuration silently defaulted"
	return true

func test_gate_configuration_is_explicit_and_single_owner() -> Variant:
	var api := SceneMultiplayer.new()
	var gate = Protocol.new()
	add_child(gate)
	var versions := [1]
	var first: Error = gate.configure(api, versions)
	versions.append(2)
	var second: Error = gate.configure(api)
	var correct: bool = first == OK and second == ERR_INVALID_PARAMETER and api.auth_callback.is_valid() and api.auth_timeout == 3.0 and not api.allow_object_decoding and gate.selected_version(1) == 0 and gate._versions == [1]
	gate.queue_free()
	await get_tree().process_frame
	return assert_true(correct, "One owner, detached config, bounded pending handshake and no selected version before evidence")

func test_invalid_configuration_does_not_install_auth_callback() -> Variant:
	var api := SceneMultiplayer.new()
	var gate = Protocol.new()
	var code: Error = gate.configure(api, [])
	var correct: bool = code == ERR_INVALID_PARAMETER and not api.auth_callback.is_valid()
	gate.free()
	return assert_true(correct, "Bad local policy cannot install a partially functioning negotiator")

func test_missing_api_and_existing_auth_owner_are_not_overwritten() -> Variant:
	var api := SceneMultiplayer.new()
	var original := func(_id: int, _bytes: PackedByteArray): pass
	api.auth_callback = original
	var gate = Protocol.new()
	var missing: Error = gate.configure(null)
	var owned: Error = gate.configure(api)
	var correct: bool = missing == ERR_INVALID_PARAMETER and owned == ERR_INVALID_PARAMETER and api.auth_callback == original
	gate.free()
	return assert_true(correct, "One negotiation owner cannot replace a pre-existing authentication policy")

func test_failed_connection_clears_previous_session_map_and_authentication() -> Variant:
	var client = get_node("/root/ClientMain")
	var previous := {}
	for field in ["pending_initial_map", "connected", "authenticated", "negotiated_protocol", "last_connection_error"]:
		previous[field] = client.get(field)
	client.pending_initial_map = {"previous_session": true}
	client.connected = true
	client.authenticated = true
	client.negotiated_protocol = 1
	client.last_connection_error = "incompatible_protocol_versions"
	client._on_connection_failed()
	var correct: bool = client.pending_initial_map.is_empty() and not client.connected and not client.authenticated and client.negotiated_protocol == 0 and client.last_connection_error == "incompatible_protocol_versions"
	for field in previous: client.set(field, previous[field])
	return assert_true(correct, "A refused connection cannot leave a map/authentication from the previous session")
