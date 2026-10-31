extends "res://tests/bot_test_suite.gd"

const Manifest = preload("res://shared/content/pack_manifest.gd")
const Registry = preload("res://shared/content/session_content_registry.gd")
const Resolver = preload("res://shared/content/pack_dependency_resolver.gd")
const LOCK_SOURCE := "offline-test/session-lock.json"

# Native contracts use honest raw manifest hashes and no filesystem/network cache.
func setup_suite() -> void: pass
func teardown_suite() -> void: pass
func setup_test() -> void: pass
func teardown_test() -> void: pass

func _manifest(creator_namespace: String, dependencies: Array = [], version: String = "1.0.0") -> Dictionary:
	return {"schema": "neptune.pack.v1", "pack_id": creator_namespace + ":pack",
		"version": version, "author": "Independent creator", "license": "Apache-2.0",
		"dependencies": dependencies.duplicate(true), "content": [{"id": creator_namespace + ":arena",
			"kind": "arena", "path": "arena.json", "sha256": "0".repeat(64)}]}

func _record(data: Dictionary) -> Dictionary:
	var text := JSON.stringify(data)
	return {"text": text, "identity": {"pack_id": data.pack_id,
		"version": data.version, "manifest_sha256": text.sha256_text()}}

func _diamond() -> Dictionary:
	var shared := _record(_manifest("graph.shared"))
	var left := _record(_manifest("graph.left", [shared.identity]))
	var right := _record(_manifest("graph.right", [shared.identity]))
	var root := _record(_manifest("graph.root", [left.identity, right.identity]))
	return {"shared": shared, "left": left, "right": right, "root": root}

func _cache(registry, records: Array, source_root: String = "cache/original/") -> bool:
	for record in records:
		var receipt: Dictionary = registry.register_manifest(record.text, source_root + record.identity.pack_id)
		if not receipt.accepted or receipt.identity != record.identity: return false
	return true

func _identities(records: Array) -> Array:
	var result := []
	for record in records: result.append(record.identity.duplicate(true))
	return result

func _rejected(result: Dictionary) -> bool:
	return result.get("accepted") == false and not str(result.get("reason", "")).is_empty() and not str(result.get("field", "")).is_empty()

func _lock_with_roots_and_packs(roots: Array, packs: Array) -> Dictionary:
	return {"schema": "neptune.manifest-lock.v1", "roots": roots.duplicate(true), "packs": packs.duplicate(true)}

func test_dependency_planning_is_pure_and_a_diamond_selects_shared_content_once() -> Variant:
	var graph := _diamond()
	var registry = Registry.new()
	if not _cache(registry, [graph.root, graph.left, graph.right, graph.shared]): return "Diamond cache setup failed"
	var planned: Dictionary = registry.resolve_roots([graph.root.identity])
	if not planned.accepted: return "A complete exact-pinned diamond failed planning"
	var expected := _lock_with_roots_and_packs([graph.root.identity], _identities([graph.left, graph.right, graph.root, graph.shared]))
	if planned.lock != expected or not registry.selection().is_empty() or registry.session_lock() != {} or registry.resolve("graph.shared:arena").accepted: return "Pure planning mutated selection or did not produce the exact deduplicated closure"
	var selected: Dictionary = registry.select_roots([graph.root.identity])
	return assert_true(selected.accepted and selected.lock == expected and registry.selection().size() == 4 and registry.resolve("graph.shared:arena").accepted and registry.resolve("graph.root:arena").accepted, "Diamond selection must include each shared dependency exactly once")

func test_root_and_cache_order_do_not_change_canonical_lock_identity() -> Variant:
	var graph := _diamond()
	var expected_json := ""
	for records in [[graph.shared, graph.left, graph.right, graph.root], [graph.root, graph.right, graph.shared, graph.left]]:
		for roots in [[graph.left.identity, graph.right.identity], [graph.right.identity, graph.left.identity]]:
			var registry = Registry.new()
			if not _cache(registry, records): return "Reordered cache setup failed"
			var result: Dictionary = registry.resolve_roots(roots)
			if not result.accepted: return "Reordered roots failed resolution"
			var canonical := JSON.stringify(result.lock, "", true)
			if result.lock_json != canonical or result.lock_sha256 != canonical.sha256_text(): return "Lock receipt does not identify canonical sorted JSON"
			if expected_json.is_empty(): expected_json = result.lock_json
			elif result.lock_json != expected_json: return "Same exact manifest bytes produced different locks based on input/cache order"
	return true

func test_repeated_identical_roots_are_deduplicated_without_changing_root_intent() -> Variant:
	var graph := _diamond()
	var registry = Registry.new()
	if not _cache(registry, [graph.shared, graph.left, graph.right, graph.root]): return "Control cache setup failed"
	var once: Dictionary = registry.resolve_roots([graph.root.identity])
	var repeated: Dictionary = registry.select_roots([graph.root.identity, graph.root.identity.duplicate(true)])
	return assert_true(once.accepted and repeated.accepted and repeated.lock == once.lock and repeated.lock.roots.size() == 1 and repeated.lock.packs.size() == 4, "Root deduplication cannot promote transitively reached dependencies into explicit roots")

func test_missing_dependency_fails_atomically_and_retry_uses_the_exact_cached_release() -> Variant:
	var graph := _diamond()
	var registry = Registry.new()
	var original := _record(_manifest("existing.original"))
	if not _cache(registry, [original, graph.left, graph.right, graph.root]) or not registry.select_roots([original.identity]).accepted: return "Control selection setup failed"
	var before_selection: Array = registry.selection().duplicate(true)
	var before_lock: Dictionary = registry.session_lock().duplicate(true)
	var refused: Dictionary = registry.select_roots([graph.root.identity])
	if not _rejected(refused) or registry.selection() != before_selection or registry.session_lock() != before_lock or registry.resolve("graph.left:arena").accepted: return "Missing transitive dependency partially changed the selected session"
	if not _cache(registry, [graph.shared]): return "Missing release could not be supplied offline"
	var accepted: Dictionary = registry.select_roots([graph.root.identity])
	return assert_true(accepted.accepted and registry.selection().size() == 5 and registry.resolve("existing.original:arena").accepted, "Supplying the exact missing release should unblock resolution without removing an existing addition")

func test_exact_dependency_versions_do_not_fall_back_to_a_newer_cached_release() -> Variant:
	var required := _record(_manifest("version.shared", [], "1.0.0"))
	var newer := _record(_manifest("version.shared", [], "2.0.0"))
	var root := _record(_manifest("version.root", [required.identity]))
	var registry = Registry.new()
	if not _cache(registry, [newer, root]): return "Version cache setup failed"
	var failed: Dictionary = registry.select_roots([root.identity])
	return assert_true(_rejected(failed) and registry.selection().is_empty() and registry.session_lock() == {}, "A cached newer release cannot satisfy an absent exact dependency")

func test_incompatible_transitive_versions_fail_without_first_loaded_wins() -> Variant:
	var first := _record(_manifest("version.shared", [], "1.0.0"))
	var second := _record(_manifest("version.shared", [], "2.0.0"))
	var left := _record(_manifest("version.left", [first.identity]))
	var right := _record(_manifest("version.right", [second.identity]))
	var registry = Registry.new()
	if not _cache(registry, [second, right, first, left]): return "Version-conflict cache setup failed"
	var result: Dictionary = registry.select_roots([left.identity, right.identity])
	return assert_true(_rejected(result) and registry.selection().is_empty() and not registry.resolve("version.left:arena").accepted, "Conflicting exact dependency versions cannot choose whichever cache/root was processed first")

func test_conflicting_dependency_hashes_never_use_an_available_unpinned_manifest() -> Variant:
	var shared := _record(_manifest("hash.shared"))
	var forged: Dictionary = shared.identity.duplicate(true)
	forged.manifest_sha256 = "f".repeat(64)
	var left := _record(_manifest("hash.left", [shared.identity]))
	var right := _record(_manifest("hash.right", [forged]))
	var registry = Registry.new()
	if not _cache(registry, [shared, left, right]): return "Hash-conflict cache setup failed"
	var result: Dictionary = registry.select_roots([left.identity, right.identity])
	return assert_true(_rejected(result) and registry.selection().is_empty(), "Cache availability cannot override a contradictory dependency digest")

func test_malformed_cyclic_graph_is_detected_before_edge_digest_verification() -> Variant:
	# A consistent raw-hash cycle would require cryptographic fixed points. These
	# honest registered bytes intentionally contain wrong edge pins; preflight
	# must diagnose the id/version cycle before any success or edge-hash fallback.
	var a := _record(_manifest("cycle.a", [{"pack_id": "cycle.b:pack", "version": "1.0.0", "manifest_sha256": "0".repeat(64)}]))
	var b := _record(_manifest("cycle.b", [{"pack_id": "cycle.c:pack", "version": "1.0.0", "manifest_sha256": "0".repeat(64)}]))
	var c := _record(_manifest("cycle.c", [{"pack_id": "cycle.a:pack", "version": "1.0.0", "manifest_sha256": "0".repeat(64)}]))
	var registry = Registry.new()
	if not _cache(registry, [a, b, c]): return "Malformed cycle fixture was not registered with its real raw hashes"
	var result: Dictionary = registry.select_roots([a.identity])
	return assert_true(_rejected(result) and result.reason == "dependency_cycle" and registry.selection().is_empty(), "Bounded cycle preflight must reject a cyclic declaration graph without trusting invented cached hashes")

func test_closure_capacity_counts_dependencies_and_preserves_previous_selection() -> Variant:
	var records := []
	for index in range(33):
		var deps: Array = [] if records.is_empty() else [records.back().identity]
		records.append(_record(_manifest("chain.node_%02d" % index, deps)))
	var registry = Registry.new()
	if not _cache(registry, records): return "Bounded chain cache setup failed"
	var boundary: Dictionary = registry.resolve_roots([records[31].identity])
	if not boundary.accepted or boundary.lock.packs.size() != 32: return "Supported dependency closure boundary was refused"
	if not registry.select_roots([records[0].identity]).accepted: return "Original root selection failed"
	var before: Dictionary = registry.session_lock().duplicate(true)
	var result: Dictionary = registry.select_roots([records[32].identity])
	return assert_true(_rejected(result) and registry.session_lock() == before and registry.selection().size() == 1, "A 33-release dependency closure cannot bypass or partially overflow the 32-pack selected budget")

func test_invalid_root_identities_are_rejected_before_mutating_selection() -> Variant:
	var record := _record(_manifest("root.valid"))
	var registry = Registry.new()
	if not _cache(registry, [record]): return "Control cache setup failed"
	for roots in [[null], [true], ["root.valid:pack"], [{}], [{"pack_id": record.identity.pack_id, "version": record.identity.version, "manifest_sha256": record.identity.manifest_sha256, "source": "somewhere"}], [{"pack_id": true, "version": "1.0.0", "manifest_sha256": "0".repeat(64)}]]:
		if not _rejected(registry.select_roots(roots)) or not registry.selection().is_empty(): return "Malformed roots altered selection or triggered missing diagnostics"
	return true

func test_bad_second_root_rolls_back_a_batch_including_a_valid_first_root() -> Variant:
	var first := _record(_manifest("batch.first"))
	var second := _record(_manifest("batch.second"))
	var existing := _record(_manifest("batch.existing"))
	var registry = Registry.new()
	if not _cache(registry, [first, second, existing]) or not registry.select_roots([existing.identity]).accepted: return "Control batch setup failed"
	var wrong: Dictionary = second.identity.duplicate(true)
	wrong.manifest_sha256 = "f".repeat(64)
	var before_selection: Array = registry.selection().duplicate(true)
	var before_lock: Dictionary = registry.session_lock().duplicate(true)
	var result: Dictionary = registry.select_roots([first.identity, wrong])
	return assert_true(_rejected(result) and registry.selection() == before_selection and registry.session_lock() == before_lock and not registry.resolve("batch.first:arena").accepted, "A late invalid root cannot leave an earlier addition partially selected")

func test_incremental_selection_retains_prior_explicit_roots_even_when_also_dependencies() -> Variant:
	var graph := _diamond()
	var registry = Registry.new()
	if not _cache(registry, [graph.shared, graph.left, graph.right, graph.root]): return "Control graph setup failed"
	if not registry.select_roots([graph.shared.identity]).accepted: return "Original explicit dependency root selection failed"
	var added: Dictionary = registry.select_roots([graph.root.identity])
	var roots := [graph.root.identity, graph.shared.identity]
	return assert_true(added.accepted and added.lock.roots == roots and added.lock.packs.size() == 4 and registry.session_lock() == added.lock, "Incremental addition must retain explicit root intent rather than silently narrowing it to the latest request")

func test_offline_lock_reuse_is_portable_across_sources_and_ignores_unrelated_cache_entries() -> Variant:
	var graph := _diamond()
	var first = Registry.new()
	if not _cache(first, [graph.shared, graph.left, graph.right, graph.root], "old/computer/"): return "Original cache setup failed"
	var planned: Dictionary = first.resolve_roots([graph.root.identity])
	if not planned.accepted: return "Original lock planning failed"
	var fresh = Registry.new()
	var unrelated := _record(_manifest("unrelated.cached"))
	var newer := _record(_manifest("graph.shared", [], "2.0.0"))
	if not _cache(fresh, [unrelated, newer, graph.root, graph.right, graph.shared, graph.left], "relocated/cache/"): return "Relocated offline cache setup failed"
	var restored: Dictionary = fresh.apply_lock(planned.lock_json, LOCK_SOURCE)
	return assert_true(restored.accepted and restored.lock_json == planned.lock_json and restored.lock_sha256 == planned.lock_sha256 and fresh.selection().size() == 4 and not fresh.resolve("unrelated.cached:arena").accepted and fresh.resolve("graph.shared:arena").descriptor.version == "1.0.0" and "old/computer/" not in restored.lock_json and "relocated/cache/" not in restored.lock_json, "Portable locks pin exact cached releases without persisting local paths or enabling unrelated/newer inventory")

func test_apply_lock_cannot_drop_an_existing_explicit_root() -> Variant:
	var graph := _diamond()
	var registry = Registry.new()
	if not _cache(registry, [graph.shared, graph.left, graph.right, graph.root]): return "Control graph setup failed"
	var narrower: Dictionary = registry.resolve_roots([graph.root.identity])
	if not narrower.accepted or not registry.select_roots([graph.shared.identity]).accepted: return "Control explicit root selection failed"
	var before: Dictionary = registry.session_lock().duplicate(true)
	var failed: Dictionary = registry.apply_lock(narrower.lock_json, LOCK_SOURCE)
	return assert_true(_rejected(failed) and registry.session_lock() == before and registry.selection().size() == 1, "Even a lock whose closure contains the old pack cannot silently remove its prior explicit-root status")

func test_expected_lock_mismatch_refuses_selection_before_any_content_commit() -> Variant:
	var first := _record(_manifest("expected.first"))
	var second := _record(_manifest("expected.second"))
	var registry = Registry.new()
	if not _cache(registry, [first, second]): return "Expected-lock cache setup failed"
	var wrong: Dictionary = registry.resolve_roots([second.identity])
	if not wrong.accepted: return "Wrong-lock control planning failed"
	var result: Dictionary = registry.select_roots([first.identity], wrong.lock)
	return assert_true(_rejected(result) and registry.selection().is_empty() and registry.session_lock() == {}, "The selection barrier must compare the complete expected lock before committing content")

func test_dependency_content_collision_cannot_overwrite_an_existing_addition() -> Variant:
	var original := _record(_manifest("collision.shared"))
	var changed := _manifest("collision.shared")
	changed.pack_id = "collision.shared:other-pack"
	changed.content[0].sha256 = "1".repeat(64)
	var conflicting := _record(changed)
	var root := _record(_manifest("collision.root", [conflicting.identity]))
	var registry = Registry.new()
	if not _cache(registry, [original, conflicting, root]) or not registry.select_roots([original.identity]).accepted: return "Content-collision control setup failed"
	var before: Dictionary = registry.session_lock().duplicate(true)
	if not _rejected(registry.resolve_roots([original.identity, root.identity])) or registry.session_lock() != before: return "Pure planning emitted a colliding content lock or changed the live session"
	var result: Dictionary = registry.select_roots([root.identity])
	return assert_true(_rejected(result) and registry.session_lock() == before and registry.resolve("collision.shared:arena").entry.sha256 == "0".repeat(64) and not registry.resolve("collision.root:arena").accepted, "Dependency expansion cannot overwrite another pack's content or partially add the requesting root")

func test_offline_lock_reuse_rejects_changed_raw_manifest_bytes_under_the_same_release() -> Variant:
	var original := _record(_manifest("immutable.root"))
	var first = Registry.new()
	if not _cache(first, [original]): return "Original immutable cache setup failed"
	var planned: Dictionary = first.resolve_roots([original.identity])
	if not planned.accepted: return "Original immutable lock planning failed"
	var altered := _manifest("immutable.root")
	altered.author = "Changed without a new release"
	var changed := _record(altered)
	var fresh = Registry.new()
	if not _cache(fresh, [changed]): return "Changed-cache control setup failed"
	var result: Dictionary = fresh.apply_lock(planned.lock_json, LOCK_SOURCE)
	return assert_true(_rejected(result) and fresh.selection().is_empty(), "An offline cache entry with the same pack/version but different raw bytes cannot satisfy an old lock")

func test_applying_a_lock_with_all_existing_roots_can_add_a_complete_dependency_closure() -> Variant:
	var graph := _diamond()
	var registry = Registry.new()
	if not _cache(registry, [graph.shared, graph.left, graph.right, graph.root]): return "Control graph setup failed"
	if not registry.select_roots([graph.shared.identity]).accepted: return "Original root selection failed"
	var planned: Dictionary = registry.resolve_roots([graph.root.identity, graph.shared.identity])
	if not planned.accepted: return "Superset lock planning failed"
	var applied: Dictionary = registry.apply_lock(planned.lock_json, LOCK_SOURCE)
	return assert_true(applied.accepted and applied.lock == planned.lock and registry.session_lock() == planned.lock and registry.selection().size() == 4, "Lock application should permit additive expansion when it retains every previous explicit root")

func test_extra_missing_or_hash_tampered_lock_members_cannot_change_the_recomputed_closure() -> Variant:
	var graph := _diamond()
	var unrelated := _record(_manifest("unused.cached"))
	var registry = Registry.new()
	if not _cache(registry, [graph.shared, graph.left, graph.right, graph.root, unrelated]): return "Tamper cache setup failed"
	var planned: Dictionary = registry.resolve_roots([graph.root.identity])
	if not planned.accepted: return "Control planning failed"
	var missing: Dictionary = planned.lock.duplicate(true)
	missing.packs.pop_back()
	var extra: Dictionary = planned.lock.duplicate(true)
	extra.packs.append(unrelated.identity)
	var changed: Dictionary = planned.lock.duplicate(true)
	changed.packs[0].manifest_sha256 = "f".repeat(64)
	for lock in [missing, extra, changed]:
		if not _rejected(registry.apply_lock(JSON.stringify(lock), LOCK_SOURCE)) or not registry.selection().is_empty() or registry.session_lock() != {}: return "A supplied lock overrode dependency closure or selected partial content"
	return true

func test_lock_parser_rejects_unknown_keys_types_schemas_duplicates_and_noncanonical_arrays() -> Variant:
	var first := _record(_manifest("parse.first"))
	var second := _record(_manifest("parse.second"))
	var canonical := _lock_with_roots_and_packs([first.identity, second.identity], [first.identity, second.identity])
	if not Resolver.validate_lock(canonical, LOCK_SOURCE).accepted: return "Valid canonical lock refused"
	var unknown: Dictionary = canonical.duplicate(true)
	unknown["source"] = "host/private/path"
	var nested: Dictionary = canonical.duplicate(true)
	nested.packs[0]["path"] = "host/private/path"
	var wrong_schema: Dictionary = canonical.duplicate(true)
	wrong_schema.schema = "neptune.manifest-lock.v999"
	var mistyped: Dictionary = canonical.duplicate(true)
	mistyped.schema = true
	var duplicate: Dictionary = canonical.duplicate(true)
	duplicate.packs.append(second.identity.duplicate(true))
	var duplicate_root: Dictionary = canonical.duplicate(true)
	duplicate_root.roots.append(second.identity.duplicate(true))
	var reversed: Dictionary = canonical.duplicate(true)
	reversed.roots.reverse()
	var reversed_packs: Dictionary = canonical.duplicate(true)
	reversed_packs.packs.reverse()
	var missing: Dictionary = canonical.duplicate(true)
	missing.erase("roots")
	for data in [null, [], true, unknown, nested, wrong_schema, mistyped, duplicate, duplicate_root, reversed, reversed_packs, missing]:
		var result: Dictionary = Resolver.validate_lock(data, LOCK_SOURCE)
		if not _rejected(result) or result.get("source") != LOCK_SOURCE: return "Invalid lock shape accepted or lost source diagnostics"
	var text := JSON.stringify(canonical)
	var duplicate_key := text.insert(1, '"schema":"neptune.manifest-lock.v0",')
	return assert_true(_rejected(Resolver.parse_lock(duplicate_key, LOCK_SOURCE)), "Duplicate lock keys cannot hide a conflicting schema")

func test_lock_validation_rejects_more_than_the_supported_closure_capacity() -> Variant:
	var packs := []
	for index in range(33): packs.append(_record(_manifest("budget.pack_%02d" % index)).identity)
	var boundary := _lock_with_roots_and_packs([packs[0]], packs.slice(0, 32))
	if not Resolver.validate_lock(boundary, LOCK_SOURCE).accepted: return "Supported 32-release lock refused structural validation"
	var overflow := _lock_with_roots_and_packs([packs[0]], packs)
	return assert_true(_rejected(Resolver.validate_lock(overflow, LOCK_SOURCE)), "A structurally valid lock cannot exceed the same selected-release budget as graph resolution")

func test_lock_identity_members_require_valid_exact_fields_and_roots_must_be_in_the_closure() -> Variant:
	var first := _record(_manifest("identity.first"))
	var canonical := _lock_with_roots_and_packs([first.identity], [first.identity])
	for patch in [{"pack_id": "not-namespaced"}, {"pack_id": true}, {"version": "latest"}, {"version": 1}, {"manifest_sha256": "a".repeat(63)}, {"manifest_sha256": null}]:
		var data: Dictionary = canonical.duplicate(true)
		data.packs[0].merge(patch, true)
		if not _rejected(Resolver.validate_lock(data, LOCK_SOURCE)): return "Malformed or non-exact locked identity accepted"
	var absent: Dictionary = canonical.duplicate(true)
	absent.roots[0].pack_id = "identity.absent:pack"
	return assert_true(_rejected(Resolver.validate_lock(absent, LOCK_SOURCE)), "Every explicit root must appear with the same exact identity in the locked closure")

func test_lock_parser_normalizes_json_whitespace_but_preserves_canonical_digest() -> Variant:
	var record := _record(_manifest("format.root"))
	var lock := _lock_with_roots_and_packs([record.identity], [record.identity])
	var canonical := JSON.stringify(lock, "", true)
	var parsed: Dictionary = Resolver.parse_lock(JSON.stringify(lock, "  ", true) + "\n", LOCK_SOURCE)
	return assert_true(parsed.accepted and parsed.lock == lock and parsed.lock_json == canonical and parsed.lock_sha256 == canonical.sha256_text(), "Whitespace does not change the canonical lock's semantic identity")

func test_lock_parser_rejects_malformed_and_oversized_documents() -> Variant:
	var record := _record(_manifest("format.root"))
	var text := JSON.stringify(_lock_with_roots_and_packs([record.identity], [record.identity]))
	for malformed in ["", "{", "not JSON", "[]", "null", text + "{}"]:
		if not _rejected(Resolver.parse_lock(malformed, LOCK_SOURCE)): return "Malformed lock document was accepted"
	var boundary := text + " ".repeat(65536 - text.to_utf8_buffer().size())
	if not Resolver.parse_lock(boundary, LOCK_SOURCE).accepted: return "Supported exact lock byte boundary refused"
	return assert_true(_rejected(Resolver.parse_lock(boundary + " ", LOCK_SOURCE)), "Whitespace cannot evade the lock document byte budget")

func test_plan_and_selected_lock_outputs_are_deeply_detached() -> Variant:
	var graph := _diamond()
	var registry = Registry.new()
	if not _cache(registry, [graph.shared, graph.left, graph.right, graph.root]): return "Control graph setup failed"
	var receipt: Dictionary = registry.select_roots([graph.root.identity])
	if not receipt.accepted: return "Control selection failed"
	var before: Dictionary = registry.session_lock().duplicate(true)
	receipt.lock.roots[0].version = "9.9.9"
	receipt.lock.packs.clear()
	var exposed: Dictionary = registry.session_lock()
	exposed.roots.clear()
	exposed.packs[0].manifest_sha256 = "f".repeat(64)
	var plan: Dictionary = registry.resolve_roots([graph.root.identity])
	if not plan.accepted: return "Repeated pure planning failed"
	plan.lock.roots[0].pack_id = "tampered.root:pack"
	return assert_true(registry.session_lock() == before and registry.selection().size() == 4 and registry.resolve("graph.shared:arena").accepted, "Returned plan, receipt and saved lock cannot mutate the live selected session")

func test_dependent_demo_fixture_pins_original_manifest_bytes_without_rewriting_them() -> Variant:
	var path := "res://demo/packs/linked/manifest.json"
	var text := FileAccess.get_file_as_string(path)
	var parsed: Dictionary = Manifest.parse(text, path)
	if not parsed.accepted or parsed.manifest.dependencies.size() != 2: return "Dependent original arena fixture missing or malformed"
	var expected := []
	for name in ["standard", "wide"]:
		var source := "res://demo/packs/%s/manifest.json" % name
		var source_text := FileAccess.get_file_as_string(source)
		var original: Dictionary = Manifest.parse(source_text, source)
		if not original.accepted: return "Existing immutable fixture missing or invalid"
		expected.append({"pack_id": original.manifest.pack_id, "version": original.manifest.version, "manifest_sha256": source_text.sha256_text()})
	var arena := FileAccess.get_file_as_bytes("res://demo/packs/linked/arena.json")
	var original := FileAccess.get_file_as_bytes("res://maps/neptune_standard.json")
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(arena)
	return assert_true(parsed.manifest.dependencies == expected and not arena.is_empty() and arena == original and parsed.manifest.content[0].sha256 == context.finish().hex_encode(), "Linked fixture must add content while pinning unchanged standard/wide manifests and preserving original arena bytes")
