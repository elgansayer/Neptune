extends "res://tests/bot_test_suite.gd"

const Download = preload("res://shared/network/content_download.gd")
const Archive = preload("res://shared/content/pack_archive.gd")
const Cache = preload("res://shared/content/pack_cache.gd")
const Registry = preload("res://shared/content/session_content_registry.gd")
const Arena = preload("res://shared/content/arena_pack_loader.gd")
var _root := ""
var _counter := 0

func setup_suite() -> void:
	_root = "user://content-sharing-tests-%d-%d" % [OS.get_process_id(), get_instance_id()]
	DirAccess.make_dir_recursive_absolute(_root)

func setup_test() -> void: pass
func teardown_test() -> void: pass
func teardown_suite() -> void: _remove(_root)

func _remove(path: String) -> void:
	var directory := DirAccess.open(path)
	if directory == null: return
	for name in directory.get_files(): DirAccess.remove_absolute(path.path_join(name))
	for name in directory.get_directories():
		if directory.is_link(name): DirAccess.remove_absolute(path.path_join(name))
		else: _remove(path.path_join(name))
	DirAccess.remove_absolute(path)

func _folder() -> String:
	_counter += 1
	return _root.path_join(str(_counter))

func _offer(bundles: Array, content_id: String = "example.standard:arena") -> Dictionary:
	var registry := Registry.new()
	var roots := []
	var by_id := {}
	for bundle in bundles:
		if not bundle.get("accepted", false): return {}
		var verified := Archive.validate(bundle.bytes, bundle.sha256, bundle.identity)
		if not verified.accepted: return {}
		var registered := registry.register_manifest(verified.manifest_text)
		if not registered.accepted: return {}
		roots.append(registered.identity)
		by_id[registered.identity.pack_id] = bundle
	var selected := registry.select_roots(roots)
	if not selected.accepted: return {}
	var archives := []
	for identity in selected.lock.packs:
		var bundle: Dictionary = by_id[identity.pack_id]
		archives.append({"identity": identity.duplicate(true), "sha256": bundle.sha256, "size_bytes": bundle.size_bytes})
	return {"type": "offer", "session_id": ("session-%d" % _counter).sha256_text(), "lock": selected.lock.duplicate(true),
		"lock_sha256": selected.lock_sha256, "content_id": content_id, "archives": archives}

func _events(client) -> Array:
	var events := []
	client.outbound.connect(func(message: Dictionary): events.append(message.duplicate(true)))
	return events

func _has(events: Array, kind: String) -> bool:
	for message in events:
		if message.type == kind: return true
	return false

func _chunk(offer: Dictionary, bundle: Dictionary, offset: int = 0) -> Dictionary:
	return {"type": "chunk", "session_id": offer.session_id, "sha256": bundle.sha256, "offset": offset,
		"data": bundle.bytes.slice(offset, mini(offset + Download.CHUNK_BYTES, bundle.bytes.size()))}

func _serve(client, offer: Dictionary, bundles: Array, events: Array) -> bool:
	var cursor := 0
	# Each valid original fixture has far fewer chunks; bound a broken helper too.
	while cursor < events.size() and cursor < 1024:
		var message: Dictionary = events[cursor]
		cursor += 1
		if message.type == "ready": return true
		if message.type == "cancel": return false
		if message.type != "request": continue
		var found := false
		for bundle in bundles:
			if bundle.sha256 == message.sha256:
				found = true
				client.receive(_chunk(offer, bundle, message.offset))
				break
		if not found: return false
	return false

func _map(loaded: Dictionary) -> Dictionary:
	var packed := PackedByteArray()
	for row in loaded.map.grid:
		for cell in row: packed.append(cell)
	return {"map_width": loaded.map.width, "map_height": loaded.map.height, "map_packed": packed,
		"map_config": {"width": loaded.map.width, "height": loaded.map.height, "tile_size": loaded.map.tile_size,
			"name": loaded.map.name, "render_geometry": true, "content": loaded.descriptor.duplicate(true),
			"selection": loaded.selection.duplicate(true), "lock": loaded.lock.duplicate(true), "lock_sha256": loaded.lock_sha256}}

func _standard() -> Dictionary: return Archive.build("res://demo/packs/standard/manifest.json")

func test_strict_offer_shape_and_exact_lock_digest_fail_without_requests() -> Variant:
	var bundle := _standard()
	var valid := _offer([bundle])
	if valid.is_empty() or not Download.validate_offer(valid).accepted: return "Original control offer failed"
	var cases := []
	for change in [{"extra": true}, {"type": "other"}, {"session_id": "wrong"}, {"content_id": "../arena"}, {"lock_sha256": "0".repeat(64)}, {"lock": {}}, {"archives": {}}]:
		var changed: Dictionary = valid.duplicate(true)
		changed.merge(change, true)
		cases.append(changed)
	var missing: Dictionary = valid.duplicate(true)
	missing.erase("content_id")
	cases.append(missing)
	for changed in cases:
		var client := Download.new(_folder())
		var events := _events(client)
		var result := client.begin(changed)
		if result.accepted or result.state != "failed" or not events.is_empty(): return "Malformed offer initiated transfer or readiness"
	return true

func test_archive_order_identity_fields_and_session_byte_caps_are_strict() -> Variant:
	var standard := _standard()
	var wide := Archive.build("res://demo/packs/wide/manifest.json")
	var valid := _offer([wide, standard])
	if valid.is_empty() or not Download.validate_offer(valid).accepted: return "Two-pack control offer failed"
	var cases := []
	var reversed: Dictionary = valid.duplicate(true)
	reversed.archives.reverse()
	cases.append(reversed)
	for change in [{"size_bytes": 0}, {"size_bytes": 1.5}, {"size_bytes": 32 * 1024 * 1024 + 1}, {"sha256": "wrong"}, {"identity": {}}, {"path": "res://source"}]:
		var changed: Dictionary = valid.duplicate(true)
		changed.archives[0].merge(change, true)
		cases.append(changed)
	var total: Dictionary = valid.duplicate(true)
	for archive in total.archives: archive.size_bytes = 17 * 1024 * 1024
	cases.append(total)
	var extra: Dictionary = valid.duplicate(true)
	extra.archives.append(extra.archives[0].duplicate(true))
	cases.append(extra)
	for changed in cases:
		if Download.validate_offer(changed).accepted: return "Invalid archive order, pin or byte budget accepted"
	return true

func test_cold_transfer_emits_ready_only_after_verified_cache_and_runtime_lock() -> Variant:
	var bundle := _standard()
	var offer := _offer([bundle])
	if offer.is_empty(): return "Control offer failed"
	var root := _folder()
	var client := Download.new(root)
	var events := _events(client)
	var before := client.begin(offer)
	if not before.accepted or before.state != "downloading" or _has(events, "ready") or Cache.new(root).lookup(bundle.identity, bundle.sha256).accepted: return "Cold transfer became ready before installation"
	if not _serve(client, offer, [bundle], events): return "Valid transfer never completed"
	var receipt := client.receipt()
	var cached := Cache.new(root).lookup(bundle.identity, bundle.sha256)
	if not cached.accepted or receipt.state != "ready" or receipt.received_bytes != bundle.bytes.size() or receipt.cache_hits != 0: return "Readiness did not represent a complete verified install"
	var loaded := Arena.load_arena(receipt.manifest_paths, offer.content_id, offer.lock)
	return loaded.accepted and loaded.lock_sha256 == offer.lock_sha256 and client.validate_initial_map(_map(loaded)).accepted and events.back() == {"type": "ready", "session_id": offer.session_id, "lock_sha256": offer.lock_sha256}

func test_warm_cache_revalidates_and_emits_ready_without_a_transfer_request() -> Variant:
	var bundle := _standard()
	var offer := _offer([bundle])
	if offer.is_empty(): return "Control offer failed"
	var root := _folder()
	if not Cache.new(root).install(bundle.bytes, bundle.sha256, bundle.identity).accepted: return "Control cache install failed"
	var client := Download.new(root)
	var events := _events(client)
	var result := client.begin(offer)
	return result.accepted and result.state == "ready" and result.cache_hits == 1 and result.received_bytes == 0 and not _has(events, "request") and _has(events, "ready") and result.lock_sha256 == offer.lock_sha256

func test_wrong_session_offset_digest_and_chunk_sizes_never_install_or_ready() -> Variant:
	var bundle := _standard()
	var offer := _offer([bundle])
	if offer.is_empty(): return "Control offer failed"
	var valid := _chunk(offer, bundle)
	var cases := []
	for spec in [
		{"change": {"session_id": "stale".sha256_text()}, "reason": "stale_content_chunk"},
		{"change": {"offset": 1}, "reason": "unexpected_content_chunk_offset"},
		{"change": {"offset": 0.0}, "reason": "unexpected_content_chunk_offset"},
		{"change": {"sha256": "0".repeat(64)}, "reason": "unexpected_content_chunk_offset"},
		{"change": {"data": valid.data.slice(0, valid.data.size() - 1)}, "reason": "content_chunk_byte_budget_exceeded"},
		{"change": {"data": PackedByteArray()}, "reason": "content_chunk_byte_budget_exceeded"},
		{"change": {"data": []}, "reason": "content_chunk_byte_budget_exceeded"},
		{"change": {"extra": true}, "reason": "invalid_content_chunk"}]:
		var changed: Dictionary = valid.duplicate(true)
		changed.merge(spec.change, true)
		cases.append({"message": changed, "reason": spec.reason})
	var oversized: Dictionary = valid.duplicate(true)
	oversized.data.append(0)
	cases.append({"message": oversized, "reason": "content_chunk_byte_budget_exceeded"})
	for spec in cases:
		var root := _folder()
		var client := Download.new(root)
		var events := _events(client)
		client.begin(offer)
		var result := client.receive(spec.message)
		if result.accepted or result.state != "failed" or result.reason != spec.reason or _has(events, "ready") or not _has(events, "cancel") or Cache.new(root).lookup(bundle.identity, bundle.sha256).accepted: return "Malformed chunk reached installed/ready content or lost its precise rejection: " + str(result)
	return true

func test_same_length_tampered_archive_is_refused_by_hash_before_activation() -> Variant:
	var bundle := _standard()
	var offer := _offer([bundle])
	if offer.is_empty(): return "Control offer failed"
	var root := _folder()
	var client := Download.new(root)
	var events := _events(client)
	client.begin(offer)
	var message := _chunk(offer, bundle)
	message.data[message.data.size() - 1] ^= 1
	var result := client.receive(message)
	return not result.accepted and result.reason == "content_install_refused:archive_hash_mismatch" and not _has(events, "ready") and not Cache.new(root).lookup(bundle.identity, bundle.sha256).accepted

func test_progress_listener_can_cancel_final_chunk_before_install_or_ready() -> Variant:
	var bundle := _standard()
	var offer := _offer([bundle])
	if offer.is_empty(): return "Control offer failed"
	var root := _folder()
	var client := Download.new(root)
	var events := _events(client)
	var cancel := func(result: Dictionary):
		if result.state == "downloading" and result.received_bytes > 0: client.cancel()
	client.status_changed.connect(cancel)
	client.begin(offer)
	var result := client.receive(_chunk(offer, bundle))
	client.status_changed.disconnect(cancel)
	return not result.accepted and result.reason == "content_cancelled" and result.received_bytes == bundle.bytes.size() and not _has(events, "ready") and _has(events, "cancel") and not Cache.new(root).lookup(bundle.identity, bundle.sha256).accepted

func test_progress_listener_can_cancel_a_cache_hit_before_outbound_ready() -> Variant:
	var bundle := _standard()
	var offer := _offer([bundle])
	if offer.is_empty(): return "Control offer failed"
	var root := _folder()
	if not Cache.new(root).install(bundle.bytes, bundle.sha256, bundle.identity).accepted: return "Control cache install failed"
	var client := Download.new(root)
	var events := _events(client)
	var cancel := func(result: Dictionary):
		if result.reason == "content_cache_hit": client.cancel()
	client.status_changed.connect(cancel)
	var result := client.begin(offer)
	client.status_changed.disconnect(cancel)
	return not result.accepted and result.reason == "content_cancelled" and result.cache_hits == 1 and result.received_bytes == 0 and not _has(events, "ready") and _has(events, "cancel") and Cache.new(root).lookup(bundle.identity, bundle.sha256).accepted

func test_expired_deadline_cancels_pending_transfer_without_readiness() -> Variant:
	var bundle := _standard()
	var offer := _offer([bundle])
	if offer.is_empty(): return "Control offer failed"
	var root := _folder()
	var client := Download.new(root)
	var events := _events(client)
	client.begin(offer)
	client._deadline = 0
	client.tick()
	var result := client.receipt()
	return not result.accepted and result.reason == "content_download_timeout" and not _has(events, "ready") and _has(events, "cancel") and not Cache.new(root).lookup(bundle.identity, bundle.sha256).accepted

func test_second_offer_cannot_replace_an_active_session() -> Variant:
	var bundle := _standard()
	var offer := _offer([bundle])
	if offer.is_empty(): return "Control offer failed"
	var client := Download.new(_folder())
	var events := _events(client)
	client.begin(offer)
	var replacement: Dictionary = offer.duplicate(true)
	replacement.session_id = "replacement".sha256_text()
	var result := client.begin(replacement)
	return not result.accepted and result.reason == "unexpected_content_offer" and client.session_id() == offer.session_id and not _has(events, "ready") and events.back() == {"type": "cancel", "session_id": offer.session_id}

func test_valid_manifest_metadata_cannot_bypass_runtime_expected_lock_recomputation() -> Variant:
	var standard := _standard()
	var wide := Archive.build("res://demo/packs/wide/manifest.json")
	var offer := _offer([standard, wide])
	if offer.is_empty(): return "Control offer failed"
	# This is a structurally valid lock whose closure includes an unrelated member.
	# The runtime must recompute all supplied explicit roots and reject it.
	offer.lock.roots.resize(1)
	offer.lock_sha256 = JSON.stringify(offer.lock, "", true).sha256_text()
	if not Download.validate_offer(offer).accepted: return "Runtime mismatch control did not pass metadata validation"
	var client := Download.new(_folder())
	var events := _events(client)
	client.begin(offer)
	_serve(client, offer, [standard, wide], events)
	var result := client.receipt()
	return not result.accepted and result.reason == "content_runtime_refused:manifest_lock_mismatch" and not _has(events, "ready") and _has(events, "cancel")

func test_initial_map_requires_readiness_exact_selection_and_bounded_geometry() -> Variant:
	var bundle := _standard()
	var offer := _offer([bundle])
	if offer.is_empty(): return "Control offer failed"
	var client := Download.new(_folder())
	if client.validate_initial_map({}).accepted: return "Map was accepted before readiness"
	var events := _events(client)
	client.begin(offer)
	if not _serve(client, offer, [bundle], events): return "Control transfer failed"
	var loaded := Arena.load_arena(client.receipt().manifest_paths, offer.content_id, offer.lock)
	if not loaded.accepted: return "Control runtime load failed"
	var valid := _map(loaded)
	if not client.validate_initial_map(valid).accepted: return "Exact initial map was rejected"
	var cases := []
	for change in [{"lock_sha256": "0".repeat(64)}, {"lock": {}}, {"content": {}}, {"selection": []}, {"width": loaded.map.width + 1}, {"height": loaded.map.height + 1}, {"tile_size": 0}, {"name": "different"}, {"render_geometry": false}]:
		var changed: Dictionary = valid.duplicate(true)
		changed.map_config.merge(change, true)
		cases.append(changed)
	for change in [{"map_width": 1}, {"map_height": 1}, {"map_packed": PackedByteArray()}, {"map_packed": []}]:
		var changed: Dictionary = valid.duplicate(true)
		changed.merge(change, true)
		cases.append(changed)
	var bad_terrain: Dictionary = valid.duplicate(true)
	bad_terrain.map_packed[0] = 3
	cases.append(bad_terrain)
	for changed in cases:
		if client.validate_initial_map(changed).accepted: return "Incompatible or malformed initial map accepted"
	# A live authority may have destroyed blocks since the original definition.
	valid.map_packed[0] = 0
	return client.validate_initial_map(valid).accepted

func test_offer_and_receipt_mutation_cannot_change_the_active_transfer_or_ready_paths() -> Variant:
	var bundle := _standard()
	var offer := _offer([bundle])
	if offer.is_empty(): return "Control offer failed"
	var saved: Dictionary = offer.duplicate(true)
	var client := Download.new(_folder())
	var events := _events(client)
	var status_mutator := func(result: Dictionary):
		result.manifest_paths.clear()
		result.state = "injected"
	client.status_changed.connect(status_mutator)
	var beginning := client.begin(offer)
	beginning.state = "injected"
	beginning.manifest_paths.append("user://wrong/manifest.json")
	offer.lock.packs.clear()
	offer.content_id = "wrong:arena"
	if not _serve(client, saved, [bundle], events): return "Detached input mutation altered the transfer"
	var first := client.receipt()
	first.manifest_paths.clear()
	client.status_changed.disconnect(status_mutator)
	return client.receipt().state == "ready" and client.receipt().manifest_paths.size() == 1 and client.receipt().lock_sha256 == saved.lock_sha256

func test_failure_cancel_keeps_old_session_when_status_listener_starts_a_new_offer() -> Variant:
	var bundle := _standard()
	var old_offer := _offer([bundle])
	if old_offer.is_empty(): return "Control offer failed"
	var next_offer: Dictionary = old_offer.duplicate(true)
	next_offer.session_id = "replacement-after-failure".sha256_text()
	var client := Download.new(_folder())
	var events := _events(client)
	var restarted := [false]
	var restart := func(result: Dictionary):
		if result.state == "failed" and not restarted[0]:
			restarted[0] = true
			client.begin(next_offer)
	client.status_changed.connect(restart)
	client.begin(old_offer)
	var bad_chunk := _chunk(old_offer, bundle)
	bad_chunk.offset = 1
	client.receive(bad_chunk)
	client.status_changed.disconnect(restart)
	var cancellations := []
	var requests := []
	for event in events:
		if event.type == "cancel": cancellations.append(event.session_id)
		if event.type == "request": requests.append(event.session_id)
	return restarted[0] and client.session_id() == next_offer.session_id and client.receipt().accepted and client.receipt().state == "downloading" and cancellations == [old_offer.session_id] and requests == [old_offer.session_id, next_offer.session_id] and not _has(events, "ready")

func test_production_client_closes_failed_ready_selection_and_drops_state_after_cleanup() -> Variant:
	var bundle := _standard()
	var offer := _offer([bundle])
	if offer.is_empty(): return "Control offer failed"
	for failure in ["invalid_map", "explicit_cancel"]:
		var download := Download.new(_folder())
		var events := _events(download)
		download.begin(offer)
		if not _serve(download, offer, [bundle], events): return "Control transfer failed"
		var loaded := Arena.load_arena(download.receipt().manifest_paths, offer.content_id, offer.lock)
		if not loaded.accepted: return "Control runtime load failed"
		var client = load("res://client/main_client.gd").new()
		# Test role bypasses only the RPC sender check. This remains the actual
		# production router, added to the tree for its real map/state forwarding path.
		add_child(client)
		client._runtime_role = "test"
		client.connected = true
		client.negotiated_protocol = 1
		client.content_download = download
		download.status_changed.connect(client._on_content_status)
		client._on_content_status(download.receipt())
		var maps := []
		var states := []
		var failures := []
		client.initial_map_received.connect(func(data: Dictionary): maps.append(data.duplicate(true)))
		client.game_state_received.connect(func(data: Dictionary): states.append(data.duplicate(true)))
		client.authentication_failed.connect(func(reason: String): failures.append(reason))
		var ping := Timer.new()
		client.add_child(ping)
		client._ping_timer = ping
		ping.start(60)
		client.auth_response({"success": true, "username": "VerifiedCreator"})
		var map := _map(loaded)
		client.receive_initial_map(map)
		client.receive_state({"control": "verified-before-failure"})
		var control: bool = client.authenticated and maps.size() == 1 and states.size() == 1 and not ping.is_stopped() and not client.pending_initial_map.is_empty()
		var reason := "content_cancelled"
		if failure == "invalid_map":
			map.map_config.lock_sha256 = "0".repeat(64)
			reason = "content_map_lock_mismatch"
			client.receive_initial_map(map)
		else:
			client.cancel_content_download()
		var failed_receipt: Dictionary = client.last_content_result
		var closed: bool = not client.connected and not client.authenticated and client.negotiated_protocol == 0 and client.last_connection_error == reason and ping.is_stopped() and client.pending_initial_map.is_empty() and failures == [reason] and maps.size() == 1 and failed_receipt.get("state") == "failed" and failed_receipt.get("reason") == reason
		client.receive_state({"late": "before-disconnect-cleanup"})
		client._on_server_disconnected()
		var preserved: bool = client.content_download == null and client.last_content_result == failed_receipt and not client.connected and not client.authenticated and client.negotiated_protocol == 0
		# An absent coordinator must not remove the account-readiness barrier on
		# a later connection, even when an old queued state reaches the router.
		client.connected = true
		client.authenticated = false
		client.receive_state({"late": "connected-without-account-readiness"})
		client.connected = false
		client.authenticated = true
		client.receive_state({"late": "disconnected-with-stale-account-flag"})
		var dropped: bool = states.size() == 1
		client.authenticated = false
		client._reset_content(true)
		client.free()
		if not control or not closed or not preserved or not dropped: return "Production client did not preserve the failed selection boundary: " + failure
	return true
