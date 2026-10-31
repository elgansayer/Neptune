extends RefCounted
class_name PackManifest

## Version 1 intentionally supports JSON map data only. No ResourceLoader or PCK mounting.
const SCHEMA := "neptune.pack/1"
const MAX_MANIFEST_BYTES := 65536
const MAX_CONTENT := 64
const MAX_DATA_BYTES := 4 * 1024 * 1024

static func failure(file: String, field: String, code: String, message: String) -> Dictionary:
	return {"ok": false, "error": {"file": file, "field": field, "code": code, "message": message}}

static func matches(value: Variant, pattern: String, limit: int) -> bool:
	if not value is String or value.length() > limit:
		return false
	var expression := RegEx.new()
	expression.compile(pattern)
	var found := expression.search(value)
	return found != null and found.get_string() == value

static func valid_id(value: Variant) -> bool:
	return matches(value, "^[a-z][a-z0-9-]*(\\.[a-z][a-z0-9-]*)+$", 96)

static func valid_version(value: Variant) -> bool:
	return matches(value, "^(0|[1-9][0-9]{0,5})\\.(0|[1-9][0-9]{0,5})\\.(0|[1-9][0-9]{0,5})$", 20)

static func valid_content_id(value: Variant, pack_id: String) -> bool:
	return value is String and value.begins_with(pack_id + ":") and matches(value.trim_prefix(pack_id + ":"), "^[a-z][a-z0-9_-]*(\\.[a-z][a-z0-9_-]*)*$", 64)

static func valid_path(value: Variant) -> bool:
	if not value is String or value.length() > 160 or not value.ends_with(".json") or value == "pack.json":
		return false
	for part in value.split("/", true):
		if not matches(part, "^[a-z0-9_-]+(\\.[a-z0-9_-]+)*$", 64):
			return false
		if matches(part.get_slice(".", 0), "^(con|prn|aux|nul|com[1-9]|lpt[1-9])$", 64):
			return false
	return true

static func fields(value: Dictionary, required: Array, file: String, field: String) -> Dictionary:
	for key in required:
		if not value.has(key):
			return failure(file, field + "." + key, "missing_field", "Required field is missing")
	for key in value:
		if key not in required:
			return failure(file, field + "." + str(key), "unknown_field", "Field is not supported by this schema")
	return {"ok": true}

static func validate(value: Variant, file: String = "pack.json") -> Dictionary:
	if not value is Dictionary:
		return failure(file, "$", "invalid_manifest", "Expected a JSON object")
	var shape := fields(value, ["schema", "id", "version", "author", "license", "provenance", "dependencies", "content"], file, "$")
	if not shape.ok: return shape
	if value.schema != SCHEMA:
		return failure(file, "$.schema", "unsupported_schema", "Supported schema: " + SCHEMA)
	if not valid_id(value.id):
		return failure(file, "$.id", "invalid_id", "Use a lowercase dotted namespace, for example example.orchard")
	if value.id.get_slice(".", 0) in ["neptune", "engine", "godot", "builtin"]:
		return failure(file, "$.id", "reserved_namespace", "First-party namespaces cannot be registered by packs")
	if not valid_version(value.version):
		return failure(file, "$.version", "invalid_version", "Use an exact major.minor.patch version")
	for key in ["author", "license", "provenance"]:
		if not value[key] is String or value[key].strip_edges().is_empty() or value[key].length() > 256:
			return failure(file, "$." + key, "invalid_text", "Expected non-empty text of at most 256 characters")
	if not value.dependencies is Array or value.dependencies.size() > 32:
		return failure(file, "$.dependencies", "invalid_dependencies", "Expected at most 32 exact dependencies")
	var dependencies := {}
	for index in range(value.dependencies.size()):
		var dependency = value.dependencies[index]
		var field := "$.dependencies[%d]" % index
		if not dependency is Dictionary:
			return failure(file, field, "invalid_dependency", "Expected an id/version object")
		shape = fields(dependency, ["id", "version"], file, field)
		if not shape.ok: return shape
		if not valid_id(dependency.id) or dependency.id == value.id:
			return failure(file, field + ".id", "invalid_dependency", "Require another namespaced pack ID")
		if not valid_version(dependency.version):
			return failure(file, field + ".version", "invalid_version", "Require an exact major.minor.patch dependency")
		if dependencies.has(dependency.id):
			return failure(file, field + ".id", "duplicate_id", "Dependency is declared twice")
		dependencies[dependency.id] = true
	if not value.content is Array or value.content.is_empty() or value.content.size() > MAX_CONTENT:
		return failure(file, "$.content", "invalid_content", "Require 1..64 content entries")
	var ids := {}
	var paths := {}
	for index in range(value.content.size()):
		var entry = value.content[index]
		var field := "$.content[%d]" % index
		if not entry is Dictionary:
			return failure(file, field, "invalid_content", "Expected a content object")
		shape = fields(entry, ["id", "type", "path", "sha256"], file, field)
		if not shape.ok: return shape
		if not valid_content_id(entry.id, value.id):
			return failure(file, field + ".id", "invalid_content_id", "Content ID must be <pack-id>:<local-name>")
		if ids.has(entry.id):
			return failure(file, field + ".id", "duplicate_id", "Content ID is declared twice")
		if entry.type != "map":
			return failure(file, field + ".type", "unsupported_content_type", "Version 1 loads data-only maps")
		if not valid_path(entry.path):
			return failure(file, field + ".path", "unsafe_path", "Use a portable lowercase relative JSON path")
		if paths.has(entry.path):
			return failure(file, field + ".path", "duplicate_path", "Content path is declared twice")
		if not matches(entry.sha256, "^[0-9a-f]{64}$", 64):
			return failure(file, field + ".sha256", "invalid_digest", "Require a lowercase SHA-256 digest")
		ids[entry.id] = true
		paths[entry.path] = true
	return {"ok": true, "manifest": value.duplicate(true)}

static func read_json(path: String, budget: int) -> Dictionary:
	if not FileAccess.file_exists(path):
		return failure(path, "$", "missing_file", "Declared JSON file is missing")
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null: return failure(path, "$", "unreadable_file", "Cannot read JSON file")
	var size := file.get_length()
	if size < 1 or size > budget:
		return failure(path, "$", "file_budget", "JSON file exceeds its byte budget or is empty")
	var bytes := file.get_buffer(size)
	file.close()
	if not _valid_utf8(bytes):
		return failure(path, "$", "invalid_utf8", "Require canonical UTF-8 JSON")
	var text := bytes.get_string_from_utf8()
	if text.to_utf8_buffer() != bytes:
		return failure(path, "$", "invalid_utf8", "Require canonical UTF-8 JSON")
	var parser := JSON.new()
	if parser.parse(text) != OK:
		return failure(path, "$", "invalid_json", "Line %d: %s" % [parser.get_error_line(), parser.get_error_message()])
	# JSON accepts duplicate object keys; packs must never rely on last-key-wins.
	var stack: Array = []
	var cursor := 0
	while cursor < text.length():
		var character := text[cursor]
		if character == "{" or character == "[":
			stack.append({} if character == "{" else null)
		elif character == "}" or character == "]":
			stack.pop_back()
		elif character == "\"":
			var start := cursor
			cursor += 1
			while cursor < text.length() and text[cursor] != "\"":
				if text[cursor] == "\\": cursor += 1
				cursor += 1
			var next := cursor + 1
			while next < text.length() and text[next] in [" ", "\t", "\r", "\n"]: next += 1
			if next < text.length() and text[next] == ":" and not stack.is_empty() and stack.back() is Dictionary:
				var key: String = JSON.parse_string(text.substr(start, cursor - start + 1))
				if stack.back().has(key):
					return failure(path, "$", "duplicate_json_key", "Duplicate object key '%s' at character %d" % [key, start])
				stack.back()[key] = true
		cursor += 1
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(bytes)
	return {"ok": true, "data": parser.data, "sha256": context.finish().hex_encode(), "bytes": size}

static func _valid_utf8(bytes: PackedByteArray) -> bool:
	# Check before decoding: malformed user data must not emit native engine errors.
	var index := 0
	while index < bytes.size():
		var first := int(bytes[index])
		if first < 128:
			index += 1
			continue
		var following := 1 if first >= 0xc2 and first <= 0xdf else (2 if first >= 0xe0 and first <= 0xef else (3 if first >= 0xf0 and first <= 0xf4 else 0))
		if following == 0 or index + following >= bytes.size(): return false
		for offset in range(1, following + 1):
			if bytes[index + offset] < 0x80 or bytes[index + offset] > 0xbf: return false
		var second := int(bytes[index + 1])
		if (first == 0xe0 and second < 0xa0) or (first == 0xed and second > 0x9f) or (first == 0xf0 and second < 0x90) or (first == 0xf4 and second > 0x8f): return false
		index += following + 1
	return true
