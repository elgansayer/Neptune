extends "res://tests/bot_test_suite.gd"

const Manifest = preload("res://shared/content/pack_manifest.gd")
const Registry = preload("res://shared/content/session_content_registry.gd")
const ArenaLoader = preload("res://shared/content/arena_pack_loader.gd")
const SOURCE := "res://creator-test/manifest.json"
var _temporary_directories: Array[String] = []

# These contracts use the real GDScript implementation without starting a game.
# Arena cases use original fixtures and disposable local authoring directories.
func setup_suite() -> void: pass
func teardown_suite() -> void: _clean_temporary_directories()
func setup_test() -> void: pass
func teardown_test() -> void: _clean_temporary_directories()

func _remove_temporary_tree(path: String) -> void:
	var directory := DirAccess.open(path)
	if directory == null: return
	for name in directory.get_files():
		DirAccess.remove_absolute(path.path_join(name))
	for name in directory.get_directories():
		if directory.is_link(name):
			DirAccess.remove_absolute(path.path_join(name))
		else:
			_remove_temporary_tree(path.path_join(name))
	DirAccess.remove_absolute(path)

func _clean_temporary_directories() -> void:
	for path in _temporary_directories:
		_remove_temporary_tree(path)
	_temporary_directories.clear()

func _write_text(path: String, text: String) -> bool:
	return _write_bytes(path, text.to_utf8_buffer())

func _write_bytes(path: String, bytes: PackedByteArray) -> bool:
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null: return false
	file.store_buffer(bytes)
	file.close()
	return true

func _arena_definition() -> Dictionary:
	return {"name": "Independent creator arena", "grid": [
		[1, 1, 1, 1, 1], [1, 0, 0, 0, 1], [1, 0, 1, 0, 1],
		[1, 0, 0, 0, 1], [1, 1, 1, 1, 1]], "spawn_points": [[1, 1], [3, 3]]}

func _arena_project(definition: Variant) -> Dictionary:
	var root := "user://pack-manifest-contract-%d-%d" % [OS.get_process_id(), Time.get_ticks_usec()]
	if DirAccess.make_dir_recursive_absolute(root) != OK: return {}
	_temporary_directories.append(root)
	var text := JSON.stringify(definition)
	var manifest := _manifest("creator.fixture")
	manifest.content[0].sha256 = text.sha256_text()
	var project := {"root": root, "manifest": manifest,
		"manifest_path": root.path_join("manifest.json"), "payload_path": root.path_join("arena.json")}
	if not _write_text(project.payload_path, text) or not _write_text(project.manifest_path, JSON.stringify(manifest)):
		return {}
	return project

func _load_project(project: Dictionary) -> Dictionary:
	if project.is_empty(): return {"accepted": false, "reason": "test_fixture_creation_failed"}
	return ArenaLoader.load_arena([project.manifest_path], project.manifest.content[0].id)

func _manifest(creator_namespace: String = "creator.test", version: String = "1.0.0") -> Dictionary:
	return {"schema": "neptune.pack.v1", "pack_id": creator_namespace + ":pack",
		"version": version, "author": "Independent creator", "license": "Apache-2.0",
		"dependencies": [], "content": [{"id": creator_namespace + ":arena", "kind": "arena",
			"path": "arena.json", "sha256": "0".repeat(64)}]}

func _parse(data: Variant) -> Dictionary:
	return Manifest.parse(JSON.stringify(data), SOURCE)

func _rejected(result: Dictionary) -> bool:
	return result.get("accepted") == false and result.get("reason", "") is String and not str(result.get("reason", "")).is_empty() and result.get("field", "") is String and not str(result.get("field", "")).is_empty() and result.get("source") == SOURCE

func _register(registry, data: Dictionary) -> Dictionary:
	return registry.register_manifest(JSON.stringify(data), SOURCE)

func _select(registry, receipt: Dictionary) -> Dictionary:
	var identity: Dictionary = receipt.identity
	return registry.select_pack(identity.pack_id, identity.version, identity.manifest_sha256)

func test_valid_manifest_preserves_exact_raw_identity_and_source() -> Variant:
	var text := JSON.stringify(_manifest(), "  ") + "\n"
	var result: Dictionary = Manifest.parse(text, SOURCE)
	return assert_true(result.accepted and result.source == SOURCE and result.manifest == _manifest() and result.manifest_sha256 == text.sha256_text(), "Receipt must identify exact UTF-8 manifest bytes and retain authoring data")

func test_namespaced_identifiers_have_a_bounded_portable_grammar() -> Variant:
	for valid in ["example.standard:arena", "creator:map_1", "a.b-c_d:sample-2", "a:" + "b".repeat(126)]:
		if not Manifest.valid_id(valid): return "Valid namespaced identifier refused: " + valid
	for invalid in [null, true, 1, [], {}, "", "arena", "author:", ":arena", "A:arena", "author:Map", "author:map:part", "author.:arena", ".author:arena", "author..team:arena", "1author:arena", "author:1arena", "author:ar/ena", "author:ar ena", "author:áréna", "author:arena\n", "a:" + "b".repeat(127)]:
		if Manifest.valid_id(invalid): return "Malformed/unbounded identifier accepted: " + str(invalid)
	return true

func test_malformed_json_and_non_object_documents_fail_with_source_diagnostics() -> Variant:
	for text in ["", "not JSON", "{", "[]", "null", "true", "1", "\"text\"", "{\"schema\":}", JSON.stringify(_manifest()) + "{}"]:
		if not _rejected(Manifest.parse(text, SOURCE)): return "Malformed document accepted or lost useful diagnostic: " + text
	return true

func test_duplicate_json_keys_cannot_hide_unknown_or_conflicting_values() -> Variant:
	var text := JSON.stringify(_manifest())
	var root_duplicate := text.insert(1, "\"schema\":\"neptune.pack.v999\",")
	var nested_duplicate := text.replace('"kind":"arena"', '"kind":"character","kind":"arena"')
	var escaped_duplicate := text.insert(1, '"schem\\u0061":"neptune.pack.v999",')
	for altered in [root_duplicate, nested_duplicate, escaped_duplicate]:
		if not _rejected(Manifest.parse(altered, SOURCE)): return "Duplicate JSON key was accepted or discarded silently"
	return true

func test_json_strings_with_key_like_text_are_valid_metadata() -> Variant:
	var data := _manifest()
	data.author = "Åsa: says \"schema\": {and} \\ text"
	return assert_true(_parse(data).accepted, "Duplicate-key scanning must respect quoted strings, escapes and Unicode author names")

func test_unknown_fields_are_rejected_at_every_manifest_level() -> Variant:
	var root := _manifest()
	root["execute"] = "controller.gd"
	var entry := _manifest()
	entry.content[0]["script"] = "controller.gd"
	var dependency := _manifest()
	dependency.dependencies = [{"pack_id": "other.creator:pack", "version": "1.0.0", "manifest_sha256": "1".repeat(64), "optional": true}]
	for data in [root, entry, dependency]:
		if not _rejected(_parse(data)): return "Unknown manifest/entry/dependency field accepted"
	return true

func test_required_fields_cannot_be_missing_or_have_wrong_types() -> Variant:
	var original := _manifest()
	for field in original:
		var missing: Dictionary = original.duplicate(true)
		missing.erase(field)
		if not _rejected(_parse(missing)): return "Missing root field accepted: " + field
		for wrong in [null, true, 42, "" if field in ["dependencies", "content"] else []]:
			var data: Dictionary = original.duplicate(true)
			data[field] = wrong
			if not _rejected(_parse(data)): return "Wrong root field type accepted: " + field
	for field in original.content[0]:
		var missing: Dictionary = original.duplicate(true)
		missing.content[0].erase(field)
		if not _rejected(_parse(missing)): return "Missing content field accepted: " + field
		for wrong in [null, true, 42, []]:
			var data: Dictionary = original.duplicate(true)
			data.content[0][field] = wrong
			if not _rejected(_parse(data)): return "Wrong content field type accepted: " + field
	return true

func test_unknown_schema_and_blank_author_or_license_are_rejected() -> Variant:
	for schema in ["neptune.pack.v0", "neptune.pack.v2", "neptune.pack", ""]:
		var data := _manifest()
		data.schema = schema
		if not _rejected(_parse(data)): return "Unknown schema accepted"
	for field in ["author", "license"]:
		for value in ["", "   ", "\n\t", "x".repeat(1025)]:
			var data := _manifest()
			data[field] = value
			if not _rejected(_parse(data)): return "Blank/unbounded credit or permission metadata accepted"
	return true

func test_only_stable_semantic_release_versions_are_accepted() -> Variant:
	for version in ["0.0.0", "1.0.0", "12.34.56"]:
		if not _parse(_manifest("creator.test", version)).accepted: return "Valid exact release refused"
	for version in ["1", "1.0", "v1.0.0", "01.0.0", "1.00.0", "1.0.01", "1.0.0-beta", "1.0.0+build", "1.0.0 ", " 1.0.0", "1.0.0\n", "1.0.-1", "1.0.0.0"]:
		if not _rejected(_parse(_manifest("creator.test", version))): return "Non-exact or unsupported release accepted: " + version
	return true

func test_reserved_roots_and_cross_namespace_content_cannot_register() -> Variant:
	for creator_namespace in ["engine", "engine.creator", "neptune", "neptune.extra", "builtin", "saturn.reference"]:
		if not _rejected(_parse(_manifest(creator_namespace))): return "Reserved engine namespace accepted: " + creator_namespace
	var cross := _manifest()
	cross.content[0].id = "another.creator:arena"
	return assert_true(_rejected(_parse(cross)), "A pack cannot register another creator's content namespace")

func test_known_content_categories_remain_distinct_from_executable_assets() -> Variant:
	for kind in ["arena", "character", "powerup", "mode", "campaign", "collection"]:
		var data := _manifest()
		data.content[0].kind = kind
		if not _parse(data).accepted: return "Supported content category refused: " + kind
	for kind in ["script", "gdextension", "scene", "Arena", "", "unknown"]:
		var data := _manifest()
		data.content[0].kind = kind
		if not _rejected(_parse(data)): return "Unsupported/executable content category accepted: " + kind
	return true

func test_content_paths_are_relative_portable_data_paths() -> Variant:
	for path in ["arena.json", "maps/room-1.json", "maps/room_2/layout.json"]:
		var data := _manifest()
		data.content[0].path = path
		if not _parse(data).accepted: return "Portable nested content path refused: " + path
	for path in ["", "/arena.json", "../arena.json", "maps/../arena.json", "./arena.json", "maps/./arena.json", "maps//arena.json", "maps\\arena.json", "res://arena.json", "user://arena.json", "C:/arena.json", "https://example.com/arena.json", "arena.json?x=1", "arena.json#fragment", "%2e%2e/arena.json", "map%20name.json", "arena.tscn", "controller.gd", "arena.JSON", "áréna.json", "arena\n.json", " arena.json", "arena.json/"]:
		var data := _manifest()
		data.content[0].path = path
		if not _rejected(_parse(data)): return "Unsafe or unsupported content path accepted: " + path
	return true

func test_hashes_are_exact_lowercase_sha256_not_arbitrary_labels() -> Variant:
	for value in ["", "a".repeat(63), "a".repeat(65), "A".repeat(64), "g".repeat(64), "sha256:" + "a".repeat(64), "0".repeat(64) + "\n"]:
		var data := _manifest()
		data.content[0].sha256 = value
		if not _rejected(_parse(data)): return "Invalid content digest accepted"
	return true

func test_content_collection_limits_include_duplicates_and_wrong_entry_types() -> Variant:
	for value in [[], [null], [true], ["arena.json"], [{}]]:
		var data := _manifest()
		data.content = value
		if not _rejected(_parse(data)): return "Empty/malformed content collection accepted"
	var duplicate := _manifest()
	duplicate.content.append(duplicate.content[0].duplicate(true))
	if not _rejected(_parse(duplicate)): return "Duplicate content ID accepted"
	var boundary := _manifest()
	boundary.content.clear()
	for index in range(128):
		boundary.content.append({"id": "creator.test:arena_%d" % index, "kind": "arena", "path": "maps/arena_%d.json" % index, "sha256": "0".repeat(64)})
	if not Manifest.validate(boundary, SOURCE).accepted: return "Maximum supported content count refused"
	boundary.content.append({"id": "creator.test:overflow", "kind": "arena", "path": "overflow.json", "sha256": "0".repeat(64)})
	return assert_true(_rejected(Manifest.validate(boundary, SOURCE)), "Content count overflow must fail before registration")

func test_dependencies_require_exact_typed_id_version_and_manifest_digest() -> Variant:
	var valid := {"pack_id": "other.creator:pack", "version": "1.0.0", "manifest_sha256": "1".repeat(64)}
	var control := _manifest()
	control.dependencies = [valid]
	if not _parse(control).accepted: return "Exact dependency declaration refused before resolution"
	for field in valid:
		var dependency: Dictionary = valid.duplicate(true)
		dependency.erase(field)
		var data := _manifest()
		data.dependencies = [dependency]
		if not _rejected(_parse(data)): return "Missing dependency field accepted: " + field
		dependency = valid.duplicate(true)
		dependency[field] = true
		data.dependencies = [dependency]
		if not _rejected(_parse(data)): return "Mistyped dependency field accepted: " + field
	for value in [[null], ["other.creator:pack"], [valid, valid.duplicate(true)]]:
		var data := _manifest()
		data.dependencies = value
		if not _rejected(_parse(data)): return "Malformed/duplicate dependency accepted"
	for patch in [{"pack_id": "not-namespaced"}, {"version": "1.0"}, {"manifest_sha256": "not-a-digest"}, {"pack_id": "creator.test:pack"}]:
		var dependency: Dictionary = valid.duplicate(true)
		dependency.merge(patch, true)
		var data := _manifest()
		data.dependencies = [dependency]
		if not _rejected(_parse(data)): return "Invalid or self-dependent release accepted"
	var overflow := _manifest()
	for index in range(32):
		overflow.dependencies.append({"pack_id": "dependency.test:pack_%d" % index, "version": "1.0.0", "manifest_sha256": "1".repeat(64)})
	if not Manifest.validate(overflow, SOURCE).accepted: return "Maximum supported dependency count refused"
	overflow.dependencies.append({"pack_id": "dependency.test:overflow", "version": "1.0.0", "manifest_sha256": "1".repeat(64)})
	return assert_true(_rejected(Manifest.validate(overflow, SOURCE)), "Dependency declarations have a finite count budget")

func test_manifest_byte_budget_is_enforced_before_parsing_including_whitespace() -> Variant:
	var text := JSON.stringify(_manifest())
	var boundary := text + " ".repeat(65536 - text.to_utf8_buffer().size())
	if not Manifest.parse(boundary, SOURCE).accepted: return "Supported exact byte boundary refused"
	return assert_true(_rejected(Manifest.parse(boundary + " ", SOURCE)), "Trailing whitespace cannot evade raw manifest byte limits")

func test_validation_detaches_nested_author_input() -> Variant:
	var data := _manifest()
	var result: Dictionary = Manifest.validate(data, SOURCE)
	if not result.accepted: return "Valid authoring object refused"
	data.content[0].path = "changed.json"
	data.content.append({"id": "creator.test:extra"})
	return assert_true(result.manifest.content.size() == 1 and result.manifest.content[0].path == "arena.json", "Validated nested content cannot alias caller-owned objects")

func test_original_arena_fixtures_identify_exact_existing_bytes() -> Variant:
	for name in ["standard", "wide"]:
		var base := "res://demo/packs/%s/" % name
		var text := FileAccess.get_file_as_string(base + "manifest.json")
		var result: Dictionary = Manifest.parse(text, base + "manifest.json")
		if not result.accepted: return "Missing or invalid real fixture manifest: " + name
		var content: Dictionary = result.manifest.content[0]
		var bytes := FileAccess.get_file_as_bytes(base + content.path)
		var source := FileAccess.get_file_as_bytes("res://maps/neptune_%s.json" % name)
		var hash_context := HashingContext.new()
		hash_context.start(HashingContext.HASH_SHA256)
		hash_context.update(bytes)
		if bytes.is_empty() or bytes != source or hash_context.finish().hex_encode() != content.sha256:
			return "Fixture replaced existing original map bytes or declared the wrong digest: " + name
	return true

func test_registration_is_idempotent_only_for_the_same_exact_release_bytes() -> Variant:
	var registry = Registry.new()
	var first := _register(registry, _manifest())
	if not first.accepted: return "First valid registration failed"
	var repeated := _register(registry, _manifest())
	var changed := _manifest()
	changed.author = "Changed without a new release"
	var refused := _register(registry, changed)
	return assert_true(repeated.accepted and repeated.identity == first.identity and not refused.accepted and registry.inventory().size() == 1, "Same release bytes are idempotent; mutated immutable releases cannot replace an inventory entry")

func test_inventory_versions_coexist_but_selected_content_cannot_be_replaced() -> Variant:
	var registry = Registry.new()
	var original := _register(registry, _manifest())
	var updated := _register(registry, _manifest("creator.test", "2.0.0"))
	if not original.accepted or not updated.accepted or registry.inventory().size() != 2: return "Immutable stored versions did not coexist"
	if not _select(registry, original).accepted: return "Original release selection failed"
	var before: Array = registry.selection().duplicate(true)
	var refused := _select(registry, updated)
	return assert_true(not refused.accepted and registry.selection() == before and registry.resolve("creator.test:arena").accepted, "Selecting another version must not replace the currently selected content")

func test_independent_additions_select_in_either_order_without_shadowing() -> Variant:
	for namespaces in [["creator.first", "creator.second"], ["creator.second", "creator.first"]]:
		var registry = Registry.new()
		for creator_namespace in namespaces:
			var receipt := _register(registry, _manifest(creator_namespace))
			if not receipt.accepted or not _select(registry, receipt).accepted: return "Independent addition refused"
		for creator_namespace in namespaces:
			var resolved: Dictionary = registry.resolve(creator_namespace + ":arena")
			if not resolved.accepted or resolved.entry.id != creator_namespace + ":arena" or resolved.entry.path != "arena.json": return "Resolved entry depended on load order or another creator's path"
		if registry.selection().size() != 2: return "Independent selected additions were discarded"
	return true

func test_inventory_is_not_implicitly_a_selected_session() -> Variant:
	var registry = Registry.new()
	if not _register(registry, _manifest()).accepted: return "Control registration failed"
	return assert_true(registry.selection().is_empty() and not registry.resolve("creator.test:arena").accepted, "Installing metadata cannot silently activate or resolve a mod")

func test_content_collision_rolls_back_the_entire_selected_addition() -> Variant:
	var registry = Registry.new()
	var original := _register(registry, _manifest())
	if not original.accepted or not _select(registry, original).accepted: return "Control registration/selection failed"
	var conflict := _manifest()
	conflict.pack_id = "creator.test:another-pack"
	conflict.content.insert(0, {"id": "creator.test:nonconflicting", "kind": "arena", "path": "other.json", "sha256": "1".repeat(64)})
	var candidate := _register(registry, conflict)
	if not candidate.accepted: return "Inventory incorrectly refused a separately selectable release"
	var before: Array = registry.selection().duplicate(true)
	var rejected := _select(registry, candidate)
	return assert_true(not rejected.accepted and registry.selection() == before and not registry.resolve("creator.test:nonconflicting").accepted and registry.resolve("creator.test:arena").entry.sha256 == "0".repeat(64), "A later colliding entry cannot leave earlier entries partially selected")

func test_forged_unknown_or_mismatched_selection_receipts_fail_atomically() -> Variant:
	var registry = Registry.new()
	var receipt := _register(registry, _manifest())
	if not receipt.accepted: return "Control registration failed"
	var identity: Dictionary = receipt.identity
	for values in [[identity.pack_id, identity.version, "f".repeat(64)], [identity.pack_id, "9.9.9", identity.manifest_sha256], ["uninstalled.creator:pack", identity.version, identity.manifest_sha256]]:
		if registry.select_pack(values[0], values[1], values[2]).accepted or not registry.selection().is_empty(): return "Forged or unavailable release changed the selected session"
	return true

func test_nonempty_dependencies_cannot_silently_start_without_a_resolver() -> Variant:
	var registry = Registry.new()
	var data := _manifest()
	data.dependencies = [{"pack_id": "other.creator:pack", "version": "1.0.0", "manifest_sha256": "1".repeat(64)}]
	var receipt := _register(registry, data)
	if not receipt.accepted: return "Metadata inventory must retain a valid unresolved dependency declaration"
	var selected := _select(registry, receipt)
	return assert_true(not selected.accepted and not str(selected.get("reason", "")).is_empty() and registry.selection().is_empty(), "Deferred dependency support must fail clearly rather than run incomplete content")

func test_registry_outputs_and_receipts_do_not_alias_authoritative_metadata() -> Variant:
	var registry = Registry.new()
	var receipt := _register(registry, _manifest())
	if not receipt.accepted or not _select(registry, receipt).accepted: return "Control registration/selection failed"
	var before_inventory: Array = registry.inventory().duplicate(true)
	var before_selection: Array = registry.selection().duplicate(true)
	var before_resolution: Dictionary = registry.resolve("creator.test:arena").duplicate(true)
	receipt.identity.version = "9.9.9"
	var inventory: Array = registry.inventory()
	inventory[0].version = "8.8.8"
	inventory.clear()
	var selected: Array = registry.selection()
	selected[0].version = "7.7.7"
	selected.clear()
	var resolved: Dictionary = registry.resolve("creator.test:arena")
	resolved.entry.path = "replacement.json"
	resolved.descriptor["author"] = "tampered"
	return assert_true(registry.inventory() == before_inventory and registry.selection() == before_selection and registry.resolve("creator.test:arena") == before_resolution, "Callers cannot mutate registry state through receipts, inventory, selection or nested resolutions")

func test_failed_registration_never_changes_existing_inventory_or_selection() -> Variant:
	var registry = Registry.new()
	var receipt := _register(registry, _manifest())
	if not receipt.accepted or not _select(registry, receipt).accepted: return "Control registration/selection failed"
	var before_inventory: Array = registry.inventory().duplicate(true)
	var before_selection: Array = registry.selection().duplicate(true)
	var invalid := _manifest("another.creator")
	invalid.content.append({"id": "neptune:replacement", "kind": "arena", "path": "arena.json", "sha256": "1".repeat(64)})
	var rejected := _register(registry, invalid)
	return assert_true(not rejected.accepted and registry.inventory() == before_inventory and registry.selection() == before_selection, "One invalid late entry must not partially register a pack or alter selected defaults")

func test_inventory_and_selection_capacity_fail_without_evicting_content() -> Variant:
	var registry = Registry.new()
	var receipts := []
	for index in range(128):
		var receipt := _register(registry, _manifest("creator.pack_%d" % index))
		if not receipt.accepted: return "Supported inventory capacity refused a unique addition"
		receipts.append(receipt)
	var before_inventory: Array = registry.inventory().duplicate(true)
	if _register(registry, _manifest("creator.overflow")).accepted or registry.inventory() != before_inventory: return "Inventory overflow evicted or admitted an extra release"
	for index in range(32):
		if not _select(registry, receipts[index]).accepted: return "Supported selected capacity refused an independent addition"
	var before_selection: Array = registry.selection().duplicate(true)
	return assert_true(not _select(registry, receipts[32]).accepted and registry.selection() == before_selection and registry.inventory() == before_inventory and registry.resolve("creator.pack_0:arena").accepted and not registry.resolve("creator.pack_32:arena").accepted, "Selection overflow cannot evict existing content or leave a partial addition")

func test_arena_adapter_resolves_two_real_original_additions_by_selected_identity() -> Variant:
	var paths := ["res://demo/packs/standard/manifest.json", "res://demo/packs/wide/manifest.json"]
	var standard: Dictionary = ArenaLoader.load_arena(paths, "example.standard:arena")
	var wide: Dictionary = ArenaLoader.load_arena(paths, "example.wide:arena")
	return assert_true(standard.accepted and wide.accepted and standard.map.width == 15 and wide.map.width == 27 and standard.map.height == 13 and wide.map.height == 13 and standard.selection.size() == 2 and wide.selection.size() == 2 and standard.descriptor.content_id == "example.standard:arena" and wide.descriptor.content_id == "example.wide:arena", "Local arena loading must resolve each addition's own JSON instead of global Stage.tscn or a fixed fallback")

func test_arena_adapter_hash_mismatch_rejects_changed_payload_before_parsing() -> Variant:
	var project := _arena_project(_arena_definition())
	if project.is_empty() or not _write_text(project.payload_path, "changed malformed bytes"): return "Temporary fixture creation failed"
	var result := _load_project(project)
	return assert_true(not result.accepted and result.reason == "definition_hash_mismatch", "Payload changes cannot be loaded under the prior immutable definition digest")

func test_arena_adapter_unknown_content_and_unsupported_runtime_kinds_fail_clearly() -> Variant:
	var project := _arena_project(_arena_definition())
	if project.is_empty(): return "Temporary fixture creation failed"
	var missing: Dictionary = ArenaLoader.load_arena([project.manifest_path], "creator.fixture:missing")
	if missing.accepted or missing.reason != "unknown_content": return "Unknown content silently selected an arena fallback"
	project.manifest.content[0].kind = "character"
	if not _write_text(project.manifest_path, JSON.stringify(project.manifest)): return "Temporary fixture update failed"
	var unsupported := _load_project(project)
	return assert_true(not unsupported.accepted and unsupported.reason == "unsupported_runtime_kind", "A recognized manifest category is not automatically executable by the arena-only adapter")

func test_arena_adapter_missing_manifest_and_definition_fail_without_engine_errors() -> Variant:
	var project := _arena_project(_arena_definition())
	if project.is_empty(): return "Temporary fixture creation failed"
	if DirAccess.remove_absolute(project.payload_path) != OK: return "Could not remove temporary payload"
	var missing_payload := _load_project(project)
	if missing_payload.accepted or missing_payload.reason != "file_missing": return "Missing arena payload did not fail clearly"
	if DirAccess.remove_absolute(project.manifest_path) != OK: return "Could not remove temporary manifest"
	var missing_manifest := _load_project(project)
	return assert_true(not missing_manifest.accepted and missing_manifest.reason == "file_missing", "A missing manifest is not an empty/default pack")

func test_arena_adapter_preflights_grid_shape_and_terrain_types() -> Variant:
	for invalid_grid in [null, [], [[0]], [[0, 0, 0], [0, 0], [0, 0, 0]], [[0, 0, 0], "row", [0, 0, 0]], [[0, 0, 0], [0, true, 0], [0, 0, 0]], [[0, 0, 0], [0, 1.5, 0], [0, 0, 0]], [[0, 0, 0], [0, 3, 0], [0, 0, 0]], [[0, 0, 0], [0, "0", 0], [0, 0, 0]]]:
		var definition := _arena_definition()
		definition.grid = invalid_grid
		var project := _arena_project(definition)
		if project.is_empty(): return "Temporary fixture creation failed"
		var result := _load_project(project)
		if result.accepted or str(result.get("reason", "")).is_empty() or str(result.get("field", "")).is_empty(): return "Invalid grid reached the legacy map parser or lost diagnostics"
	return true

func test_arena_adapter_preflights_spawn_structure_bounds_and_occupancy() -> Variant:
	for invalid_spawns in [null, [], [[1]], [[1, 1, 2]], [[true, 1]], [[1.5, 1]], [[-1, 1]], [[5, 1]], [[1, 5]], [["1", 1]], [[1, 1], [1, 1]], [[0, 0]], [[2, 2]], [{"x": 1, "y": 1, "extra": 2}], [{"x": 1}]]:
		var definition := _arena_definition()
		definition.spawn_points = invalid_spawns
		var project := _arena_project(definition)
		if project.is_empty(): return "Temporary fixture creation failed"
		var result := _load_project(project)
		if result.accepted or str(result.get("reason", "")).is_empty() or str(result.get("field", "")).is_empty(): return "Invalid/duplicate/blocked spawn reached the legacy map parser or lost diagnostics"
	return true

func test_arena_adapter_preflights_optional_metadata_before_legacy_parser() -> Variant:
	for patch in [{"metadata": []}, {"metadata": "text"}, {"name": true}, {"author": {}}, {"description": 123}, {"name": "x".repeat(513)}]:
		var definition := _arena_definition()
		definition.merge(patch, true)
		var project := _arena_project(definition)
		if project.is_empty(): return "Temporary fixture creation failed"
		var result := _load_project(project)
		if result.accepted or str(result.get("field", "")).is_empty(): return "Invalid metadata entered the legacy parser without a useful error"
	return true

func test_arena_adapter_rejects_malformed_or_ambiguous_definition_json() -> Variant:
	for text in ["{", "[]", "null", '{"grid":[],"grid":[]}']:
		var project := _arena_project(_arena_definition())
		if project.is_empty(): return "Temporary fixture creation failed"
		project.manifest.content[0].sha256 = text.sha256_text()
		if not _write_text(project.payload_path, text) or not _write_text(project.manifest_path, JSON.stringify(project.manifest)): return "Temporary fixture update failed"
		var result := _load_project(project)
		if result.accepted or str(result.get("reason", "")).is_empty(): return "Malformed/ambiguous definition JSON was loaded"
	return true

func test_arena_adapter_payload_symlink_cannot_escape_declared_file_boundary() -> Variant:
	if OS.has_feature("web"): return true # Native CI exercises symlinks; browsers have no host symlink API.
	var project := _arena_project(_arena_definition())
	if project.is_empty(): return "Temporary fixture creation failed"
	var text := FileAccess.get_file_as_string(project.payload_path)
	var actual: String = project.root.path_join("actual.json")
	if not _write_text(actual, text) or DirAccess.remove_absolute(project.payload_path) != OK: return "Temporary symlink fixture setup failed"
	var directory := DirAccess.open(project.root)
	if directory == null or directory.create_link(ProjectSettings.globalize_path(actual), "arena.json") != OK: return "Native symlink fixture creation unavailable"
	var result := _load_project(project)
	return assert_true(not result.accepted and result.reason == "unsafe_definition_path", "Even hash-matching arena bytes must not be read through a payload symlink")

func test_arena_adapter_intermediate_directory_symlink_is_refused() -> Variant:
	if OS.has_feature("web"): return true # Native CI exercises symlinks; browsers have no host symlink API.
	var project := _arena_project(_arena_definition())
	if project.is_empty(): return "Temporary fixture creation failed"
	var actual: String = project.root.path_join("actual")
	if DirAccess.make_dir_recursive_absolute(actual) != OK or not _write_text(actual.path_join("arena.json"), JSON.stringify(_arena_definition())): return "Temporary directory-link fixture setup failed"
	var directory := DirAccess.open(project.root)
	if directory == null or directory.create_link(ProjectSettings.globalize_path(actual), "linked") != OK: return "Native directory symlink fixture creation unavailable"
	project.manifest.content[0].path = "linked/arena.json"
	if not _write_text(project.manifest_path, JSON.stringify(project.manifest)): return "Temporary manifest update failed"
	var result := _load_project(project)
	return assert_true(not result.accepted and result.reason == "unsafe_definition_path", "A symlinked directory cannot redirect relative arena definition resolution")

func test_utf8_preflight_accepts_canonical_unicode_and_rejects_malformed_encodings() -> Variant:
	if not Manifest.valid_utf8("Åsa 日本語 🙂".to_utf8_buffer()): return "Canonical Unicode author data was refused"
	for bytes in [PackedByteArray([0xff]), PackedByteArray([0x80]), PackedByteArray([0xc0, 0xaf]), PackedByteArray([0xe0, 0x80, 0xaf]), PackedByteArray([0xed, 0xa0, 0x80]), PackedByteArray([0xf4, 0x90, 0x80, 0x80]), PackedByteArray([0xe2, 0x82]), PackedByteArray([0xf0, 0x9f, 0x99])]:
		if Manifest.valid_utf8(bytes): return "Noncanonical, surrogate, truncated or invalid UTF-8 accepted before engine decoding"
	return true

func test_arena_adapter_invalid_manifest_utf8_is_rejected_before_engine_decoding() -> Variant:
	var project := _arena_project(_arena_definition())
	if project.is_empty() or not _write_bytes(project.manifest_path, PackedByteArray([0xff, 0xfe])): return "Temporary invalid UTF-8 manifest creation failed"
	var result := _load_project(project)
	return assert_true(not result.accepted and result.reason == "invalid_utf8", "Invalid manifest bytes must produce a normal receipt without engine decoder errors")

func test_arena_adapter_invalid_payload_utf8_is_rejected_even_with_matching_hash() -> Variant:
	var project := _arena_project(_arena_definition())
	if project.is_empty(): return "Temporary fixture creation failed"
	var bytes := PackedByteArray([0xed, 0xa0, 0x80])
	var hash_context := HashingContext.new()
	hash_context.start(HashingContext.HASH_SHA256)
	hash_context.update(bytes)
	project.manifest.content[0].sha256 = hash_context.finish().hex_encode()
	if not _write_bytes(project.payload_path, bytes) or not _write_text(project.manifest_path, JSON.stringify(project.manifest)): return "Temporary invalid UTF-8 payload creation failed"
	var result := _load_project(project)
	return assert_true(not result.accepted and result.reason == "invalid_utf8", "A digest cannot make invalid encoded data safe to decode")

func test_arena_adapter_manifest_file_symlink_is_refused_before_reading() -> Variant:
	if OS.has_feature("web"): return true # Native CI exercises symlinks; browsers have no host symlink API.
	var project := _arena_project(_arena_definition())
	if project.is_empty(): return "Temporary fixture creation failed"
	var actual: String = project.root.path_join("actual-manifest.json")
	if not _write_text(actual, JSON.stringify(project.manifest)) or DirAccess.remove_absolute(project.manifest_path) != OK: return "Temporary manifest-link fixture setup failed"
	var directory := DirAccess.open(project.root)
	if directory == null or directory.create_link(ProjectSettings.globalize_path(actual), "manifest.json") != OK: return "Native manifest symlink fixture creation unavailable"
	var result := _load_project(project)
	return assert_true(not result.accepted and result.reason == "unsafe_definition_path", "Manifest symlinks must be refused as well as payload symlinks")

func test_arena_adapter_manifest_ancestor_symlink_is_refused_before_reading() -> Variant:
	if OS.has_feature("web"): return true # Native CI exercises symlinks; browsers have no host symlink API.
	var project := _arena_project(_arena_definition())
	if project.is_empty(): return "Temporary fixture creation failed"
	var actual: String = project.root.path_join("actual")
	if DirAccess.make_dir_recursive_absolute(actual) != OK or not _write_text(actual.path_join("manifest.json"), JSON.stringify(project.manifest)) or not _write_text(actual.path_join("arena.json"), JSON.stringify(_arena_definition())): return "Temporary manifest-directory fixture setup failed"
	var directory := DirAccess.open(project.root)
	if directory == null or directory.create_link(ProjectSettings.globalize_path(actual), "linked") != OK: return "Native manifest-directory symlink fixture creation unavailable"
	var result: Dictionary = ArenaLoader.load_arena([project.root.path_join("linked/manifest.json")], project.manifest.content[0].id)
	return assert_true(not result.accepted and result.reason == "unsafe_definition_path", "A manifest's ancestor directory cannot redirect the selected local content root")
