extends "res://tests/bot_test_suite.gd"

const Archive = preload("res://shared/content/pack_archive.gd")
const Manifest = preload("res://shared/content/pack_manifest.gd")
const STANDARD := "res://demo/packs/standard/manifest.json"
const RUBY := "res://demo/characters/ruby/manifest.json"
var _root := ""
var _counter := 0

func setup_suite() -> void:
	_root = "user://pack-archive-tests-%d-%d" % [OS.get_process_id(), get_instance_id()]
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

func _write(path: String, bytes: PackedByteArray) -> bool:
	if DirAccess.make_dir_recursive_absolute(path.get_base_dir()) != OK: return false
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null: return false
	file.store_buffer(bytes)
	file.close()
	return true

func _hash(bytes: PackedByteArray) -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	if not bytes.is_empty(): context.update(bytes)
	return context.finish().hex_encode()

func _identity(text: String) -> Dictionary:
	var data: Dictionary = JSON.parse_string(text)
	return {"pack_id": data.pack_id, "version": data.version, "manifest_sha256": _hash(text.to_utf8_buffer())}

func _u32(value: int) -> PackedByteArray:
	var bytes := PackedByteArray()
	bytes.resize(4)
	bytes.encode_u32(0, value)
	return bytes

# Construct adversarial wire bytes independently from the implementation builder.
func _envelope(text: String, records: Array, count: int = -1) -> PackedByteArray:
	var bytes := "NEPTPK01".to_ascii_buffer()
	var manifest_bytes := text.to_utf8_buffer()
	bytes.append_array(_u32(manifest_bytes.size()))
	bytes.append_array(manifest_bytes)
	bytes.append_array(_u32(records.size() if count < 0 else count))
	for record in records:
		var name: PackedByteArray = record.path.to_utf8_buffer()
		bytes.append_array(_u32(name.size()))
		bytes.append_array(name)
		bytes.append_array(_u32(record.get("declared_size", record.bytes.size())))
		bytes.append_array(record.bytes)
	return bytes

func _standard_text() -> String: return FileAccess.get_file_as_string(STANDARD)
func _arena_bytes() -> PackedByteArray: return FileAccess.get_file_as_bytes(STANDARD.get_base_dir().path_join("arena.json"))
func _refused(result: Dictionary) -> bool:
	return result.get("accepted") == false and not str(result.get("reason", "")).is_empty() and not str(result.get("field", "")).is_empty()

func _check(bytes: PackedByteArray, text: String = "") -> Dictionary:
	return Archive.validate(bytes, _hash(bytes), _identity(_standard_text() if text.is_empty() else text))

func test_original_arena_archive_is_deterministic_and_binds_exact_raw_manifest() -> Variant:
	var first := Archive.build(STANDARD)
	var second := Archive.build(STANDARD)
	if not first.accepted or not second.accepted: return "Original arena could not be packaged"
	var raw := FileAccess.get_file_as_bytes(STANDARD)
	var checked := Archive.validate(first.bytes, first.sha256, first.identity)
	return first.bytes == second.bytes and first.sha256 == _hash(first.bytes) and first.sha256 == second.sha256 and first.size_bytes == first.bytes.size() and checked.accepted and checked.identity == _identity(raw.get_string_from_utf8()) and checked.manifest_text.to_utf8_buffer() == raw and checked.files.size() == 1 and checked.files["arena.json"] == _arena_bytes()

func test_original_character_includes_deduplicated_hash_bound_raw_pixels() -> Variant:
	var built := Archive.build(RUBY)
	if not built.accepted: return "Original character could not be packaged"
	var checked := Archive.validate(built.bytes, built.sha256, built.identity)
	return checked.accepted and checked.files.size() == 2 and checked.files["character.json"] == FileAccess.get_file_as_bytes(RUBY.get_base_dir().path_join("character.json")) and checked.files["frames/idle.rgba"] == FileAccess.get_file_as_bytes(RUBY.get_base_dir().path_join("frames/idle.rgba"))

func test_dependent_release_can_be_validated_before_its_dependency_is_installed() -> Variant:
	var built := Archive.build("res://demo/packs/linked/manifest.json")
	if not built.accepted: return "Independent release packaging incorrectly required an installed dependency closure"
	var checked := Archive.validate(built.bytes, built.sha256, built.identity)
	return checked.accepted and checked.manifest.dependencies.size() == 2

func test_expected_archive_digest_and_manifest_identity_are_both_required() -> Variant:
	var built := Archive.build(STANDARD)
	if not built.accepted: return "Control archive build failed"
	var wrong: Dictionary = built.identity.duplicate(true)
	wrong.manifest_sha256 = "0".repeat(64)
	if not _refused(Archive.validate(built.bytes, "0".repeat(64), built.identity)): return "Wrong archive digest was trusted"
	if not _refused(Archive.validate(built.bytes, built.sha256, wrong)): return "Wrong manifest digest was trusted"
	for identity in [{}, {"pack_id": true, "version": "1.0.0", "manifest_sha256": "0".repeat(64)}, {"pack_id": built.identity.pack_id, "version": "2.0.0", "manifest_sha256": built.identity.manifest_sha256}]:
		if not _refused(Archive.validate(built.bytes, built.sha256, identity)): return "Malformed or wrong expected release identity was trusted"
	return true

func test_unknown_or_compressed_formats_are_rejected_without_a_decompressor() -> Variant:
	for bytes in [PackedByteArray(), "PK\u0003\u0004compressed".to_utf8_buffer(), PackedByteArray([31, 139, 8, 0]), "NEPTPK02".to_ascii_buffer(), "NEPTPK01".to_ascii_buffer()]:
		if not _refused(_check(bytes)): return "Unknown, compressed or incomplete archive format was accepted"
	return true

func test_every_truncated_header_boundary_and_trailing_bytes_are_rejected() -> Variant:
	var text := _standard_text()
	var valid := _envelope(text, [{"path": "arena.json", "bytes": _arena_bytes()}])
	if not _check(valid).accepted: return "Independent valid stored envelope failed"
	for length in [0, 7, 8, 11, 12, 12 + text.to_utf8_buffer().size(), valid.size() - 1]:
		if not _refused(_check(valid.slice(0, length))): return "Truncated archive accepted at boundary " + str(length)
	valid.append(0)
	return _refused(_check(valid))

func test_declared_lengths_counts_and_whole_archive_budget_are_bounded() -> Variant:
	var text := _standard_text()
	var manifest_overflow := "NEPTPK01".to_ascii_buffer()
	manifest_overflow.append_array(_u32(65537))
	var manifest_wrap := "NEPTPK01".to_ascii_buffer()
	manifest_wrap.append_array(_u32(4294967295))
	for bytes in [manifest_overflow, manifest_wrap, _envelope(text, [], 513), _envelope(text, [], 4294967295), _envelope(text, [{"path": "arena.json", "bytes": PackedByteArray(), "declared_size": 4294967295}])]:
		if not _refused(_check(bytes)): return "Oversized or overflowing declared archive budget accepted"
	var whole := PackedByteArray()
	whole.resize(32 * 1024 * 1024 + 1)
	return _refused(_check(whole))

func test_unsafe_portable_paths_never_reach_materialization() -> Variant:
	for path in ["../arena.json", "/arena.json", "a/../arena.json", "a//arena.json", "a\\arena.json", "res://arena.json", "https://host/arena.json", "%2e%2e/arena.json", "a\narena.json", "é.json", "manifest.json", "script.gd", "scene.tscn", "library.so", "a/" + "x".repeat(251) + ".json", "d/".repeat(16) + "arena.json"]:
		var bytes := _envelope(_standard_text(), [{"path": path, "bytes": _arena_bytes()}])
		if not _refused(_check(bytes)): return "Unsafe archive path accepted: " + path
	return true

func test_declared_unique_directory_prefixes_are_bounded_before_installation() -> Variant:
	var manifest: Dictionary = JSON.parse_string(_standard_text())
	manifest.content = []
	var records := []
	var arena := _arena_bytes()
	for index in 128:
		var path := "dir_%03d/a/b/c/d/e/f/g/h/arena.json" % index
		manifest.content.append({"id": "example.standard:arena_%03d" % index, "kind": "arena", "path": path, "sha256": _hash(arena)})
		records.append({"path": path, "bytes": arena})
	var text := JSON.stringify(manifest)
	return _refused(_check(_envelope(text, records), text))

func test_duplicate_case_colliding_unsorted_and_undeclared_records_are_rejected() -> Variant:
	var arena := _arena_bytes()
	for records in [
		[{"path": "arena.json", "bytes": arena}, {"path": "arena.json", "bytes": arena}],
		[{"path": "ARENA.json", "bytes": arena}, {"path": "arena.json", "bytes": arena}],
		[{"path": "A/x.json", "bytes": arena}, {"path": "a/y.json", "bytes": arena}],
		[{"path": "z.json", "bytes": arena}, {"path": "arena.json", "bytes": arena}],
		[{"path": "arena.json", "bytes": arena}, {"path": "unused.json", "bytes": "{}".to_utf8_buffer()}],
		[]]:
		if not _refused(_check(_envelope(_standard_text(), records))): return "Ambiguous, extra or missing record accepted"
	return true

func test_hash_matching_outer_archive_cannot_hide_changed_definition_bytes() -> Variant:
	var changed := _arena_bytes()
	changed[changed.size() - 2] ^= 1
	return _refused(_check(_envelope(_standard_text(), [{"path": "arena.json", "bytes": changed}])))

func test_file_directory_prefix_collision_is_rejected_before_installation() -> Variant:
	var manifest: Dictionary = JSON.parse_string(_standard_text())
	var nested: Dictionary = manifest.content[0].duplicate(true)
	nested.id = "example.standard:nested"
	nested.path = "arena.json/child.json"
	manifest.content.append(nested)
	var text := JSON.stringify(manifest)
	return _refused(_check(_envelope(text, [{"path": "arena.json", "bytes": _arena_bytes()}, {"path": "arena.json/child.json", "bytes": _arena_bytes()}]), text))

func test_invalid_utf8_manifest_is_refused_without_engine_decoding_errors() -> Variant:
	var bytes := "NEPTPK01".to_ascii_buffer()
	bytes.append_array(_u32(1))
	bytes.append(255)
	bytes.append_array(_u32(1))
	return _refused(_check(bytes))

func test_honest_hashes_cannot_make_invalid_arena_semantics_acceptable() -> Variant:
	var data: Dictionary = JSON.parse_string(_arena_bytes().get_string_from_utf8())
	data.grid[0][0] = 999
	var bytes := JSON.stringify(data).to_utf8_buffer()
	var manifest: Dictionary = JSON.parse_string(_standard_text())
	manifest.content[0].sha256 = _hash(bytes)
	var text := JSON.stringify(manifest)
	return _refused(_check(_envelope(text, [{"path": "arena.json", "bytes": bytes}]), text))

func test_honest_hashes_cannot_make_unsupported_content_executable() -> Variant:
	var manifest: Dictionary = JSON.parse_string(_standard_text())
	manifest.content[0].kind = "powerup"
	var text := JSON.stringify(manifest)
	return _refused(_check(_envelope(text, [{"path": "arena.json", "bytes": _arena_bytes()}]), text))

func test_character_pixel_length_hash_and_metadata_are_verified_inside_archive() -> Variant:
	var text := FileAccess.get_file_as_string(RUBY)
	var character := FileAccess.get_file_as_bytes(RUBY.get_base_dir().path_join("character.json"))
	var pixels := FileAccess.get_file_as_bytes(RUBY.get_base_dir().path_join("frames/idle.rgba"))
	for bad_pixels in [pixels.slice(0, pixels.size() - 1), PackedByteArray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])]:
		var archive := _envelope(text, [{"path": "character.json", "bytes": character}, {"path": "frames/idle.rgba", "bytes": bad_pixels}])
		if not _refused(_check(archive, text)): return "Malformed raw pixels passed archive validation"
	var data: Dictionary = JSON.parse_string(character.get_string_from_utf8())
	data.fallback = "missing"
	character = JSON.stringify(data).to_utf8_buffer()
	var manifest: Dictionary = JSON.parse_string(text)
	manifest.content[0].sha256 = _hash(character)
	text = JSON.stringify(manifest)
	return _refused(_check(_envelope(text, [{"path": "character.json", "bytes": character}, {"path": "frames/idle.rgba", "bytes": pixels}]), text))

func test_builder_cannot_follow_source_manifest_or_payload_symlinks() -> Variant:
	if OS.has_feature("web"): return true # Native CI owns host symlink rejection.
	_counter += 1
	var folder := _root.path_join(str(_counter))
	DirAccess.make_dir_recursive_absolute(folder)
	var directory := DirAccess.open(folder)
	if directory.create_link(ProjectSettings.globalize_path(STANDARD), "manifest.json") != OK: return "Native manifest symlink fixture unavailable"
	if not _refused(Archive.build(folder.path_join("manifest.json"))): return "Builder followed a manifest symlink"
	DirAccess.remove_absolute(folder.path_join("manifest.json"))
	if not _write(folder.path_join("manifest.json"), FileAccess.get_file_as_bytes(STANDARD)): return "Manifest copy failed"
	if directory.create_link(ProjectSettings.globalize_path(STANDARD.get_base_dir().path_join("arena.json")), "arena.json") != OK: return "Native payload symlink fixture unavailable"
	return _refused(Archive.build(folder.path_join("manifest.json")))

func test_builder_only_packages_declared_data_from_an_authoring_directory() -> Variant:
	_counter += 1
	var folder := _root.path_join(str(_counter))
	for name in ["manifest.json", "arena.json"]:
		if not _write(folder.path_join(name), FileAccess.get_file_as_bytes(STANDARD.get_base_dir().path_join(name))): return "Fixture copy failed"
	if not _write(folder.path_join("ignored.gd"), "extends Node\n".to_utf8_buffer()): return "Undeclared source fixture failed"
	var built := Archive.build(folder.path_join("manifest.json"))
	if not built.accepted: return "Builder could not package declared original data"
	var checked := Archive.validate(built.bytes, built.sha256, built.identity)
	return checked.accepted and checked.files.size() == 1 and checked.files.has("arena.json") and not checked.files.has("ignored.gd")
