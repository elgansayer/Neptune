extends RefCounted

## Whole-archive content-addressed cache. Only a complete verified directory is
## published; partial stages are never addressed by lookup or selected in a room.
const Manifest = preload("res://shared/content/pack_manifest.gd")
const Archive = preload("res://shared/content/pack_archive.gd")
const Definitions = preload("res://shared/content/arena_pack_loader.gd")

var root: String

func _init(cache_root: String = "user://pack-cache") -> void:
	root = cache_root

func _failure(reason: String, field: String = "cache") -> Dictionary:
	return Manifest.failure(reason, field, root)

func _directory(path: String, create: bool = false) -> Dictionary:
	if not path.begins_with("user://") or not Manifest.valid_manifest_path(path.path_join("sentinel.json")):
		return _failure("invalid_cache_path")
	var current := "user://"
	for part in path.trim_prefix("user://").split("/"):
		var directory := DirAccess.open(current)
		if directory == null: return _failure("cache_directory_unreadable")
		if directory.is_link(part): return _failure("unsafe_cache_symlink")
		var next := current.path_join(part)
		if FileAccess.file_exists(next): return _failure("cache_path_is_file")
		if not DirAccess.dir_exists_absolute(next):
			if not create: return _failure("cache_miss")
			if directory.make_dir(part) != OK: return _failure("cache_directory_create_failed")
		current = next
	return {"accepted": true}

func _read_regular(directory: String, relative: String, maximum: int) -> Dictionary:
	var located := Definitions._definition_path(directory, relative)
	if not located.accepted: return located
	var file := FileAccess.open(located.path, FileAccess.READ)
	if file == null: return _failure("cached_file_missing", relative)
	var size := file.get_length()
	if size > maximum:
		file.close()
		return _failure("cached_file_byte_budget_exceeded", relative)
	var bytes := file.get_buffer(size)
	file.close()
	if bytes.size() != size: return _failure("cached_file_truncated", relative)
	return {"accepted": true, "bytes": bytes}

func _check_content(directory: String, verified: Dictionary) -> Dictionary:
	var expected: Dictionary = verified.files.duplicate()
	expected["manifest.json"] = verified.manifest_text.to_utf8_buffer()
	var expected_directories := {}
	for relative in expected:
		var parent: String = relative.get_base_dir()
		while not parent.is_empty():
			expected_directories[parent] = true
			parent = parent.get_base_dir()
	for relative in expected:
		var read := _read_regular(directory, relative, Archive.MAX_ARCHIVE_BYTES)
		if not read.accepted: return read
		if read.bytes != expected[relative]: return _failure("cached_file_changed", relative)
	# A cache entry is an immutable materialization, not a directory to augment.
	var pending := [directory]
	var seen := 0
	var visited := 0
	while not pending.is_empty():
		visited += 1
		if visited > expected_directories.size() + 1: return _failure("cached_directory_budget_exceeded")
		var path: String = pending.pop_back()
		var access := DirAccess.open(path)
		if access == null: return _failure("cache_directory_unreadable")
		access.include_hidden = true
		for name in access.get_directories():
			if access.is_link(name): return _failure("unsafe_cache_symlink")
			var child := path.path_join(name)
			var relative: String = child.trim_prefix(directory + "/")
			if not expected_directories.has(relative): return _failure("undeclared_cached_directory", relative)
			pending.append(child)
		for name in access.get_files():
			if access.is_link(name): return _failure("unsafe_cache_symlink")
			var relative: String = path.path_join(name).trim_prefix(directory + "/")
			if not expected.has(relative): return _failure("undeclared_cached_file", relative)
			seen += 1
			if seen > Archive.MAX_FILES + 1: return _failure("cached_file_budget_exceeded")
	if seen != expected.size(): return _failure("cached_file_count_mismatch")
	return {"accepted": true}

func archive_path(archive_sha256: String) -> String:
	if not Manifest.valid_hash(archive_sha256): return ""
	return root.path_join(archive_sha256).path_join("archive.npack")

func lookup(identity: Dictionary, archive_sha256: String) -> Dictionary:
	if not Manifest.valid_hash(archive_sha256) or not Archive._valid_identity(identity):
		return _failure("invalid_cache_identity", "identity")
	var ready := root.path_join(archive_sha256)
	var safe := _directory(ready)
	if not safe.accepted: return safe
	var access := DirAccess.open(ready)
	if access != null: access.include_hidden = true
	if access == null or access.get_files() != PackedStringArray(["archive.npack"]) or access.get_directories() != PackedStringArray(["content"]):
		return _failure("immutable_cache_entry_shape_mismatch")
	var read := _read_regular(ready, "archive.npack", Archive.MAX_ARCHIVE_BYTES)
	if not read.accepted: return read
	var verified := Archive.validate(read.bytes, archive_sha256, identity)
	if not verified.accepted: return verified
	var content := ready.path_join("content")
	safe = _directory(content)
	if not safe.accepted: return safe
	var checked := _check_content(content, verified)
	if not checked.accepted: return checked
	return {"accepted": true, "reason": "cache_verified", "identity": identity.duplicate(true),
		"archive_sha256": archive_sha256, "manifest_path": content.path_join("manifest.json"), "reused": true}

func _write(directory: String, relative: String, bytes: PackedByteArray) -> Dictionary:
	var path := directory.path_join(relative)
	var safe := _directory(path.get_base_dir(), true)
	if not safe.accepted: return safe
	var access := DirAccess.open(path.get_base_dir())
	if access == null or access.is_link(path.get_file()) or FileAccess.file_exists(path) or DirAccess.dir_exists_absolute(path):
		return _failure("cache_write_conflict", relative)
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null: return _failure("cache_write_failed", relative)
	file.store_buffer(bytes)
	file.flush()
	var error := file.get_error()
	file.close()
	if error != OK: return _failure("cache_write_failed", relative)
	return {"accepted": true}

func _discard_stage(stage: String) -> void:
	# Only our freshly generated stage is ever removed. Refuse links throughout.
	if not stage.begins_with(root + "/.stage-") or not _directory(stage).accepted: return
	var stack := [stage]
	var directories := []
	var budget := Archive.MAX_DIRECTORIES + 4
	while not stack.is_empty() and budget > 0:
		budget -= 1
		var path: String = stack.pop_back()
		var access := DirAccess.open(path)
		if access == null: return
		access.include_hidden = true
		directories.append(path)
		for name in access.get_files():
			if access.is_link(name): return
			access.remove(name)
		for name in access.get_directories():
			if access.is_link(name): return
			stack.append(path.path_join(name))
	if not stack.is_empty(): return
	directories.reverse()
	for path in directories: DirAccess.remove_absolute(path)

func install(bytes: PackedByteArray, archive_sha256: String, identity: Dictionary) -> Dictionary:
	# Complete validation precedes any cache directory/file creation.
	var verified := Archive.validate(bytes, archive_sha256, identity)
	if not verified.accepted: return verified
	var safe := _directory(root, true)
	if not safe.accepted: return safe
	var ready := root.path_join(archive_sha256)
	var access := DirAccess.open(root)
	if access.is_link(archive_sha256) or FileAccess.file_exists(ready) or DirAccess.dir_exists_absolute(ready):
		var existing := lookup(identity, archive_sha256)
		if existing.accepted: return existing
		return _failure("immutable_cache_entry_conflict")
	var random := Crypto.new().generate_random_bytes(16)
	if random.size() != 16: return _failure("cache_stage_random_failed")
	var stage := root.path_join(".stage-" + random.hex_encode())
	if access.make_dir(stage.get_file()) != OK: return _failure("cache_stage_create_failed")
	var written := _write(stage, "archive.npack", bytes)
	if written.accepted:
		written = _write(stage.path_join("content"), "manifest.json", verified.manifest_text.to_utf8_buffer())
	if written.accepted:
		var paths: Array = verified.files.keys()
		paths.sort()
		for path in paths:
			written = _write(stage.path_join("content"), path, verified.files[path])
			if not written.accepted: break
	if written.accepted:
		written = _check_content(stage.path_join("content"), verified)
	if not written.accepted:
		_discard_stage(stage)
		return written
	# The target is immutable and nonempty. Concurrent successful publication is
	# reused; an existing corrupt/conflicting entry is never removed or repaired.
	if DirAccess.rename_absolute(stage, ready) != OK:
		_discard_stage(stage)
		var concurrent := lookup(identity, archive_sha256)
		if concurrent.accepted: return concurrent
		return _failure("cache_publish_failed")
	var result := lookup(identity, archive_sha256)
	if not result.accepted: return result
	result["reason"] = "cache_installed"
	result["reused"] = false
	return result
