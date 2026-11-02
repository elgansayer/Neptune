extends RefCounted

## A deterministic stored-only data envelope. No compression, links, resources,
## executable records or platform archive decoder participates in this format.
const Manifest = preload("res://shared/content/pack_manifest.gd")
const Definitions = preload("res://shared/content/arena_pack_loader.gd")
const Characters = preload("res://shared/content/character_pack_loader.gd")
const MAGIC := "NEPTPK01"
const MAX_ARCHIVE_BYTES := 32 * 1024 * 1024
const MAX_FILES := 512
const MAX_PATH_BYTES := 256
const MAX_PATH_DEPTH := 16
const MAX_DIRECTORIES := 1024

static func _failure(reason: String, field: String, source: String = "") -> Dictionary:
	return Manifest.failure(reason, field, source)

static func _identity(manifest: Dictionary, digest: String) -> Dictionary:
	return {"pack_id": manifest.pack_id, "version": manifest.version, "manifest_sha256": digest}

static func _valid_identity(identity: Dictionary) -> bool:
	return Manifest._keys(identity, ["pack_id", "version", "manifest_sha256"], "identity", "").accepted \
		and Manifest.valid_id(identity.pack_id) and not Manifest._reserved(identity.pack_id) \
		and Manifest.valid_version(identity.version) and Manifest.valid_hash(identity.manifest_sha256)

static func valid_path(path: Variant) -> bool:
	if not path is String or path == "manifest.json" or path.length() > MAX_PATH_BYTES:
		return false
	var json_path: String = path.trim_suffix(".rgba") + ".json" if path.ends_with(".rgba") else path
	if not Manifest.valid_path(json_path): return false
	if path.split("/").size() > MAX_PATH_DEPTH: return false
	# Avoid case/device-name aliases when materializing on desktop platforms.
	for part in path.split("/"):
		if part.ends_with("."): return false
		var base: String = part.get_slice(".", 0).to_upper()
		if base in ["CON", "PRN", "AUX", "NUL"]: return false
		if base.length() == 4 and base.substr(0, 3) in ["COM", "LPT"] and base[3] in "123456789": return false
	return path.ends_with(".json") or path.ends_with(".rgba")

static func _decode_json(bytes: PackedByteArray, source: String) -> Dictionary:
	if bytes.size() > Manifest.MAX_MANIFEST_BYTES:
		return _failure("json_byte_budget_exceeded", "$", source)
	if not Manifest.valid_utf8(bytes): return _failure("invalid_utf8", "$", source)
	var text := bytes.get_string_from_utf8()
	if text.to_utf8_buffer() != bytes: return _failure("noncanonical_utf8", "$", source)
	var parsed := Manifest.parse_json(text, source)
	if parsed.accepted: parsed["text"] = text
	return parsed

static func _check_files(manifest: Dictionary, files: Dictionary) -> Dictionary:
	var expected := {}
	var aliases := {"manifest.json": true}
	var directories := {}
	var directory_aliases := {}
	for path in files:
		if not valid_path(path) or not files[path] is PackedByteArray:
			return _failure("invalid_archive_path_or_payload", "files:" + str(path))
		if aliases.has(path.to_lower()): return _failure("duplicate_archive_path", "files:" + path)
		aliases[path.to_lower()] = true
	for path in files:
		var prefix := ""
		var parts: PackedStringArray = path.split("/")
		for index in parts.size() - 1:
			prefix = parts[index] if prefix.is_empty() else prefix + "/" + parts[index]
			if aliases.has(prefix.to_lower()): return _failure("archive_file_directory_collision", "files:" + path)
			if directory_aliases.has(prefix.to_lower()) and directory_aliases[prefix.to_lower()] != prefix:
				return _failure("archive_directory_case_collision", "files:" + path)
			directory_aliases[prefix.to_lower()] = prefix
			directories[prefix] = true
			if directories.size() > MAX_DIRECTORIES: return _failure("archive_directory_budget_exceeded", "files")
	# Validate every declared definition, even when a room selects only one of them.
	for entry in manifest.content:
		if entry.kind not in ["arena", "character"]:
			return _failure("unsupported_archive_kind", "content.kind")
		if not valid_path(entry.path) or not files.has(entry.path):
			return _failure("archive_definition_missing", "content.path:" + entry.path)
		var bytes: PackedByteArray = files[entry.path]
		if Definitions._digest(bytes) != entry.sha256:
			return _failure("definition_hash_mismatch", "content.sha256:" + entry.path)
		var parsed := _decode_json(bytes, entry.path)
		if not parsed.accepted: return parsed
		expected[entry.path] = true
		if entry.kind == "arena":
			var checked := Definitions._check_map(parsed.data, entry.path)
			if not checked.accepted: return checked
		else:
			var checked := Characters.validate(parsed.data, entry.path)
			if not checked.accepted: return checked
			for path in checked.images:
				if not valid_path(path) or not files.has(path):
					return _failure("archive_pixel_missing", path, entry.path)
				var image: Dictionary = checked.images[path]
				var pixels: PackedByteArray = files[path]
				if pixels.size() != image.width * image.height * 4:
					return _failure("pixel_byte_length_mismatch", path, entry.path)
				if Definitions._digest(pixels) != image.sha256:
					return _failure("pixel_hash_mismatch", path, entry.path)
				expected[path] = true
	if files.size() != expected.size(): return _failure("undeclared_archive_file", "files")
	return {"accepted": true}

static func validate(bytes: PackedByteArray, expected_sha256: String, expected_identity: Dictionary) -> Dictionary:
	if not Manifest.valid_hash(expected_sha256) or not _valid_identity(expected_identity):
		return _failure("invalid_archive_identity", "identity")
	if bytes.size() < 16 or bytes.size() > MAX_ARCHIVE_BYTES:
		return _failure("archive_byte_budget_exceeded", "archive")
	if Definitions._digest(bytes) != expected_sha256:
		return _failure("archive_hash_mismatch", "archive.sha256")
	if bytes.slice(0, 8) != MAGIC.to_ascii_buffer(): return _failure("unsupported_archive_format", "archive.magic")
	var manifest_size := int(bytes.decode_u32(8))
	var offset := 12
	# Subtraction avoids trusting attacker-supplied length arithmetic.
	if manifest_size < 1 or manifest_size > Manifest.MAX_MANIFEST_BYTES or manifest_size > bytes.size() - offset - 4:
		return _failure("invalid_archive_manifest_length", "archive.manifest")
	var document := _decode_json(bytes.slice(offset, offset + manifest_size), "archive/manifest.json")
	if not document.accepted: return document
	var parsed := Manifest.parse(document.text, "archive/manifest.json")
	if not parsed.accepted: return parsed
	var identity := _identity(parsed.manifest, parsed.manifest_sha256)
	if identity != expected_identity: return _failure("archive_manifest_identity_mismatch", "identity")
	offset += manifest_size
	var count := int(bytes.decode_u32(offset))
	offset += 4
	if count < 1 or count > MAX_FILES: return _failure("archive_file_budget_exceeded", "archive.files")
	var files := {}
	var previous := ""
	var aliases := {"manifest.json": true}
	for index in count:
		var field := "archive.files[%d]" % index
		if bytes.size() - offset < 4: return _failure("truncated_archive", field)
		var path_size := int(bytes.decode_u32(offset))
		offset += 4
		if path_size < 1 or path_size > MAX_PATH_BYTES or path_size > bytes.size() - offset - 4:
			return _failure("invalid_archive_path_length", field + ".path")
		var path_bytes := bytes.slice(offset, offset + path_size)
		for value in path_bytes:
			if value < 33 or value > 126: return _failure("invalid_archive_path", field + ".path")
		var path := path_bytes.get_string_from_ascii()
		offset += path_size
		if not valid_path(path) or path <= previous or aliases.has(path.to_lower()):
			return _failure("invalid_duplicate_or_unsorted_archive_path", field + ".path")
		previous = path
		aliases[path.to_lower()] = true
		var size := int(bytes.decode_u32(offset))
		offset += 4
		if size > bytes.size() - offset: return _failure("truncated_archive", field + ".bytes")
		files[path] = bytes.slice(offset, offset + size)
		offset += size
	if offset != bytes.size(): return _failure("trailing_archive_bytes", "archive")
	var checked := _check_files(parsed.manifest, files)
	if not checked.accepted: return checked
	return {"accepted": true, "reason": "archive_verified", "files": files,
		"manifest_text": document.text, "manifest": parsed.manifest.duplicate(true), "identity": identity,
		"sha256": expected_sha256, "size_bytes": bytes.size()}

static func _read_file(root: String, relative: String, maximum: int) -> Dictionary:
	if not valid_path(relative): return _failure("invalid_archive_path", relative, root)
	var located := Definitions._definition_path(root, relative)
	if not located.accepted: return located
	var file := FileAccess.open(located.path, FileAccess.READ)
	if file == null: return _failure("archive_source_missing", relative, root)
	if file.get_length() > maximum:
		file.close()
		return _failure("archive_source_byte_budget_exceeded", relative, root)
	var size := file.get_length()
	var bytes := file.get_buffer(size)
	file.close()
	if bytes.size() != size: return _failure("archive_source_truncated", relative, root)
	return {"accepted": true, "bytes": bytes}

static func _append_u32(bytes: PackedByteArray, value: int) -> void:
	var start := bytes.size()
	bytes.resize(start + 4)
	bytes.encode_u32(start, value)

static func build(manifest_path: String) -> Dictionary:
	if not Manifest.valid_manifest_path(manifest_path): return _failure("invalid_manifest_path", "manifest_path", manifest_path)
	var document := Definitions._read(manifest_path)
	if not document.accepted: return document
	var parsed := Manifest.parse(document.text, manifest_path)
	if not parsed.accepted: return parsed
	var root := manifest_path.get_base_dir()
	var files := {}
	var total: int = document.text.to_utf8_buffer().size() + 16
	for entry in parsed.manifest.content:
		if entry.kind not in ["arena", "character"]: return _failure("unsupported_archive_kind", "content.kind", manifest_path)
		if not files.has(entry.path):
			var read := _read_file(root, entry.path, Manifest.MAX_MANIFEST_BYTES)
			if not read.accepted: return read
			files[entry.path] = read.bytes
			total += read.bytes.size() + entry.path.length() + 8
			if total > MAX_ARCHIVE_BYTES: return _failure("archive_byte_budget_exceeded", "archive", manifest_path)
		if entry.kind == "character":
			var definition := _decode_json(files[entry.path], entry.path)
			if not definition.accepted: return definition
			var checked := Characters.validate(definition.data, entry.path)
			if not checked.accepted: return checked
			for path in checked.images:
				if not files.has(path):
					var image: Dictionary = checked.images[path]
					var read := _read_file(root, path, image.width * image.height * 4)
					if not read.accepted: return read
					files[path] = read.bytes
					total += read.bytes.size() + path.length() + 8
					if files.size() > MAX_FILES or total > MAX_ARCHIVE_BYTES:
						return _failure("archive_byte_or_file_budget_exceeded", "archive", manifest_path)
	if files.size() > MAX_FILES: return _failure("archive_file_budget_exceeded", "archive.files", manifest_path)
	var bytes := MAGIC.to_ascii_buffer()
	var manifest_bytes: PackedByteArray = document.text.to_utf8_buffer()
	_append_u32(bytes, manifest_bytes.size())
	bytes.append_array(manifest_bytes)
	_append_u32(bytes, files.size())
	var paths: Array = files.keys()
	paths.sort()
	for path in paths:
		var path_bytes: PackedByteArray = path.to_ascii_buffer()
		_append_u32(bytes, path_bytes.size())
		bytes.append_array(path_bytes)
		_append_u32(bytes, files[path].size())
		bytes.append_array(files[path])
	var digest := Definitions._digest(bytes)
	var identity := _identity(parsed.manifest, parsed.manifest_sha256)
	var checked := validate(bytes, digest, identity)
	if not checked.accepted: return checked
	return {"accepted": true, "reason": "archive_built", "bytes": bytes, "sha256": digest,
		"size_bytes": bytes.size(), "identity": identity, "files_count": files.size()}
