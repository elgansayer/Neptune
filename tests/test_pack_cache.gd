extends "res://tests/bot_test_suite.gd"

const Archive = preload("res://shared/content/pack_archive.gd")
const Cache = preload("res://shared/content/pack_cache.gd")
const Arenas = preload("res://shared/content/arena_pack_loader.gd")
const Characters = preload("res://shared/content/character_pack_loader.gd")
const STANDARD := "res://demo/packs/standard/manifest.json"
var _root := ""
var _counter := 0

func setup_suite() -> void:
	_root = "user://pack-cache-tests-%d-%d" % [OS.get_process_id(), get_instance_id()]
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

func _folder() -> String:
	_counter += 1
	return _root.path_join(str(_counter))

func _refused(result: Dictionary) -> bool:
	return result.get("accepted") == false and not str(result.get("reason", "")).is_empty() and not str(result.get("field", "")).is_empty()

func test_cold_install_materializes_exact_data_and_reuses_existing_arena_loader() -> Variant:
	var built := Archive.build(STANDARD)
	if not built.accepted: return "Control archive failed"
	var cache := Cache.new(_folder())
	var installed := cache.install(built.bytes, built.sha256, built.identity)
	if not installed.accepted or installed.reused: return "Cold install failed or incorrectly claimed cache reuse"
	var loaded := Arenas.load_arena([installed.manifest_path], "example.standard:arena")
	return loaded.accepted and loaded.descriptor.manifest_sha256 == built.identity.manifest_sha256 and FileAccess.get_file_as_bytes(installed.manifest_path) == FileAccess.get_file_as_bytes(STANDARD) and FileAccess.get_file_as_bytes(installed.manifest_path.get_base_dir().path_join("arena.json")) == FileAccess.get_file_as_bytes(STANDARD.get_base_dir().path_join("arena.json"))

func test_original_character_installs_without_executable_resources() -> Variant:
	var built := Archive.build("res://demo/characters/ruby/manifest.json")
	if not built.accepted: return "Original character archive failed"
	var cache := Cache.new(_folder())
	var installed := cache.install(built.bytes, built.sha256, built.identity)
	if not installed.accepted: return "Original character install failed"
	var loaded := Characters.load_character([installed.manifest_path], "example.ruby:character")
	if not loaded.accepted: return "Installed character did not load through existing native adapter"
	var visual := Characters.create_visual(loaded)
	var valid := visual != null and visual.get_script() == null and visual.get_node("AnimatedSprite2D").get_script() == null
	if visual != null: visual.free()
	return valid

func test_repeat_install_and_a_fresh_cache_object_reuse_one_immutable_release() -> Variant:
	var built := Archive.build(STANDARD)
	if not built.accepted: return "Control archive failed"
	var root := _folder()
	var cache := Cache.new(root)
	var first := cache.install(built.bytes, built.sha256, built.identity)
	if not first.accepted: return "Cold install failed"
	var second := cache.install(built.bytes, built.sha256, built.identity)
	var offline := Cache.new(root).lookup(built.identity, built.sha256)
	var directory := DirAccess.open(root)
	return second.accepted and second.reused and offline.accepted and offline.reused and first.manifest_path == second.manifest_path and second.manifest_path == offline.manifest_path and directory.get_directories().size() == 1 and directory.get_files().is_empty()

func test_wrong_digest_or_identity_cannot_create_an_installation() -> Variant:
	var built := Archive.build(STANDARD)
	if not built.accepted: return "Control archive failed"
	var root := _folder()
	var cache := Cache.new(root)
	var wrong: Dictionary = built.identity.duplicate(true)
	wrong.version = "9.0.0"
	if not _refused(cache.install(built.bytes, "0".repeat(64), built.identity)): return "Wrong archive hash installed"
	if not _refused(cache.install(built.bytes, built.sha256, wrong)): return "Wrong release identity installed"
	return _refused(cache.lookup(built.identity, built.sha256))

func test_a_failed_new_archive_preserves_a_previously_installed_release() -> Variant:
	var first := Archive.build(STANDARD)
	var other := Archive.build("res://demo/packs/wide/manifest.json")
	if not first.accepted or not other.accepted: return "Control archives failed"
	var cache := Cache.new(_folder())
	var old := cache.install(first.bytes, first.sha256, first.identity)
	if not old.accepted: return "Original install failed"
	var manifest_before := FileAccess.get_file_as_bytes(old.manifest_path)
	var truncated: PackedByteArray = other.bytes.slice(0, other.bytes.size() - 1)
	if not _refused(cache.install(truncated, _hash(truncated), other.identity)): return "Truncated new archive installed"
	var still_ready := cache.lookup(first.identity, first.sha256)
	return still_ready.accepted and still_ready.manifest_path == old.manifest_path and FileAccess.get_file_as_bytes(old.manifest_path) == manifest_before and _refused(cache.lookup(other.identity, other.sha256))

func test_additional_versions_preserve_the_old_version_bytes_and_path() -> Variant:
	var first := Archive.build(STANDARD)
	if not first.accepted: return "Control archive failed"
	var source := _folder()
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(STANDARD))
	manifest.version = "2.0.0"
	if not _write(source.path_join("manifest.json"), JSON.stringify(manifest).to_utf8_buffer()) or not _write(source.path_join("arena.json"), FileAccess.get_file_as_bytes(STANDARD.get_base_dir().path_join("arena.json"))): return "New original version fixture failed"
	var second := Archive.build(source.path_join("manifest.json"))
	if not second.accepted: return "New version could not be packaged"
	var cache := Cache.new(_folder())
	var old := cache.install(first.bytes, first.sha256, first.identity)
	var added := cache.install(second.bytes, second.sha256, second.identity)
	if not old.accepted or not added.accepted: return "Versions did not coexist"
	return old.manifest_path != added.manifest_path and cache.lookup(first.identity, first.sha256).accepted and cache.lookup(second.identity, second.sha256).accepted and FileAccess.get_file_as_bytes(old.manifest_path) == FileAccess.get_file_as_bytes(STANDARD)

func test_interrupted_staging_is_invisible_to_lookup_and_does_not_block_retry() -> Variant:
	var built := Archive.build(STANDARD)
	if not built.accepted: return "Control archive failed"
	var root := _folder()
	var orphan := root.path_join(".stage-interrupted/content/manifest.json")
	if not _write(orphan, FileAccess.get_file_as_bytes(STANDARD)): return "Interrupted fixture setup failed"
	var cache := Cache.new(root)
	if not _refused(cache.lookup(built.identity, built.sha256)): return "Incomplete staging was considered ready"
	var installed := cache.install(built.bytes, built.sha256, built.identity)
	return installed.accepted and installed.manifest_path != orphan and FileAccess.get_file_as_bytes(orphan) == FileAccess.get_file_as_bytes(STANDARD)

func test_preexisting_partial_final_directory_is_never_activated_or_overwritten() -> Variant:
	var built := Archive.build(STANDARD)
	if not built.accepted: return "Control archive failed"
	var root := _folder()
	var partial := root.path_join(built.sha256).path_join("content/manifest.json")
	var sentinel := "incomplete-previous-attempt".to_utf8_buffer()
	if not _write(partial, sentinel): return "Partial final fixture failed"
	var cache := Cache.new(root)
	return _refused(cache.lookup(built.identity, built.sha256)) and _refused(cache.install(built.bytes, built.sha256, built.identity)) and FileAccess.get_file_as_bytes(partial) == sentinel

func test_materialized_payload_tampering_invalidates_lookup_and_is_not_silently_repaired() -> Variant:
	var built := Archive.build(STANDARD)
	if not built.accepted: return "Control archive failed"
	var cache := Cache.new(_folder())
	var installed := cache.install(built.bytes, built.sha256, built.identity)
	if not installed.accepted: return "Control install failed"
	var path: String = installed.manifest_path.get_base_dir().path_join("arena.json")
	var tampered := "{}".to_utf8_buffer()
	if not _write(path, tampered): return "Tamper fixture failed"
	return _refused(cache.lookup(built.identity, built.sha256)) and _refused(cache.install(built.bytes, built.sha256, built.identity)) and FileAccess.get_file_as_bytes(path) == tampered

func test_retained_archive_tampering_invalidates_lookup_even_when_materialized_files_match() -> Variant:
	var built := Archive.build(STANDARD)
	if not built.accepted: return "Control archive failed"
	var root := _folder()
	var cache := Cache.new(root)
	var installed := cache.install(built.bytes, built.sha256, built.identity)
	if not installed.accepted: return "Control install failed"
	if not _write(root.path_join(built.sha256).path_join("archive.npack"), "changed".to_utf8_buffer()): return "Archive tamper fixture failed"
	return _refused(cache.lookup(built.identity, built.sha256)) and FileAccess.get_file_as_bytes(installed.manifest_path) == FileAccess.get_file_as_bytes(STANDARD)

func test_extra_files_and_empty_directories_do_not_augment_a_verified_installation() -> Variant:
	var built := Archive.build(STANDARD)
	if not built.accepted: return "Control archive failed"
	for relative in ["extra.json", ".extra.json", "content/extra.json", "content/.extra.json", "content/empty", "content/.empty", "content/deep/empty"]:
		var root := _folder()
		var cache := Cache.new(root)
		var installed := cache.install(built.bytes, built.sha256, built.identity)
		if not installed.accepted: return "Control install failed"
		var added := root.path_join(built.sha256).path_join(relative)
		if relative.ends_with(".json"):
			if not _write(added, "{}".to_utf8_buffer()): return "Extra file setup failed"
		elif DirAccess.make_dir_recursive_absolute(added) != OK: return "Empty directory setup failed"
		if not _refused(cache.lookup(built.identity, built.sha256)): return "Undeclared cache content was accepted: " + relative
	return true

func test_lookup_requires_the_requested_archive_and_exact_manifest_identity() -> Variant:
	var built := Archive.build(STANDARD)
	if not built.accepted: return "Control archive failed"
	var cache := Cache.new(_folder())
	if not cache.install(built.bytes, built.sha256, built.identity).accepted: return "Control install failed"
	var wrong: Dictionary = built.identity.duplicate(true)
	wrong.manifest_sha256 = "f".repeat(64)
	return _refused(cache.lookup(built.identity, "0".repeat(64))) and _refused(cache.lookup(wrong, built.sha256)) and _refused(cache.lookup({}, built.sha256))

func test_cache_root_and_existing_content_symlinks_cannot_redirect_install_or_lookup() -> Variant:
	if OS.has_feature("web"): return true # Native CI owns host symlink rejection.
	var built := Archive.build(STANDARD)
	if not built.accepted: return "Control archive failed"
	var outside := _folder()
	DirAccess.make_dir_recursive_absolute(outside)
	var directory := DirAccess.open(_root)
	_counter += 1
	var link_name := "link-%d" % _counter
	if directory.create_link(ProjectSettings.globalize_path(outside), link_name) != OK: return "Native cache symlink fixture unavailable"
	var redirected := Cache.new(_root.path_join(link_name).path_join("nested"))
	if not _refused(redirected.install(built.bytes, built.sha256, built.identity)): return "Cache install followed a root ancestor symlink"
	if not DirAccess.open(outside).get_directories().is_empty(): return "Refused root symlink still wrote outside the cache"
	var cache := Cache.new(_folder())
	var installed := cache.install(built.bytes, built.sha256, built.identity)
	if not installed.accepted: return "Control install failed"
	var payload: String = installed.manifest_path.get_base_dir().path_join("arena.json")
	if DirAccess.remove_absolute(payload) != OK: return "Payload symlink setup failed"
	if DirAccess.open(payload.get_base_dir()).create_link(ProjectSettings.globalize_path(STANDARD.get_base_dir().path_join("arena.json")), "arena.json") != OK: return "Native payload symlink fixture unavailable"
	return _refused(cache.lookup(built.identity, built.sha256))
