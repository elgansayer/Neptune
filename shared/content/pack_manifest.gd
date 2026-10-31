extends RefCounted

## Portable definition metadata. This class never loads resources or executes code.
const SCHEMA := "neptune.pack.v1"
const MAX_MANIFEST_BYTES := 65536
const MAX_CONTENT := 128
const MAX_DEPENDENCIES := 32
const KINDS := ["arena", "character", "powerup", "mode", "campaign", "collection"]
const RESERVED := ["engine", "neptune", "builtin", "saturn"]

static func failure(reason: String, field: String, source: String = "") -> Dictionary:
	return {"accepted": false, "reason": reason, "field": field, "source": source}

static func valid_id(value: Variant) -> bool:
	if not value is String or value.length() > 128:
		return false
	return RegEx.create_from_string("^[a-z][a-z0-9_-]*(\\.[a-z][a-z0-9_-]*)*:[a-z][a-z0-9_-]*\\z").search(value) != null

static func valid_hash(value: Variant) -> bool:
	return value is String and RegEx.create_from_string("^[0-9a-f]{64}\\z").search(value) != null

static func valid_version(value: Variant) -> bool:
	return value is String and value.length() <= 32 and RegEx.create_from_string("^(0|[1-9][0-9]{0,8})\\.(0|[1-9][0-9]{0,8})\\.(0|[1-9][0-9]{0,8})\\z").search(value) != null

static func valid_path(value: Variant) -> bool:
	if not value is String or value.is_empty() or value.length() > 256 or not value.ends_with(".json"):
		return false
	if value.begins_with("/") or RegEx.create_from_string("^[A-Za-z0-9_./-]+\\z").search(value) == null:
		return false
	for part in value.split("/", true):
		if part.is_empty() or part in [".", ".."]:
			return false
	return true

static func valid_manifest_path(path: Variant) -> bool:
	if not path is String or path.length() > 512 or not path.ends_with(".json"):
		return false
	if not path.begins_with("res://") and not path.begins_with("user://"):
		return false
	if "\\" in path or "?" in path or "#" in path or "%" in path:
		return false
	for part in path.substr(path.find("://") + 3).split("/", true):
		if part.is_empty() or part in [".", ".."] or ":" in part:
			return false
		for index in part.length():
			if part.unicode_at(index) < 32 or part.unicode_at(index) == 127:
				return false
	return true

## Check canonical UTF-8 before engine decoding, which logs/replaces bad bytes.
static func valid_utf8(bytes: PackedByteArray) -> bool:
	var index := 0
	while index < bytes.size():
		var first := bytes[index]
		if first < 0x80:
			index += 1
			continue
		var width := 0
		if first >= 0xc2 and first <= 0xdf: width = 2
		elif first >= 0xe0 and first <= 0xef: width = 3
		elif first >= 0xf0 and first <= 0xf4: width = 4
		else: return false
		if index + width > bytes.size(): return false
		var second := bytes[index + 1]
		if first == 0xe0 and second < 0xa0: return false
		if first == 0xed and second > 0x9f: return false
		if first == 0xf0 and second < 0x90: return false
		if first == 0xf4 and second > 0x8f: return false
		for offset in range(1, width):
			if bytes[index + offset] < 0x80 or bytes[index + offset] > 0xbf:
				return false
		index += width
	return true

static func _text(value: Variant, limit: int) -> bool:
	if not value is String or value.is_empty() or value.length() > limit or value != value.strip_edges():
		return false
	for index in value.length():
		if value.unicode_at(index) < 32 or value.unicode_at(index) == 127:
			return false
	return true

static func _reserved(id: String) -> bool:
	return id.get_slice(":", 0).get_slice(".", 0) in RESERVED

static func _keys(value: Dictionary, expected: Array, field: String, source: String) -> Dictionary:
	for key in value:
		if key not in expected:
			return failure("unknown_field", field + "." + str(key), source)
	for key in expected:
		if not value.has(key):
			return failure("missing_field", field + "." + key, source)
	return {"accepted": true}

## Reject ambiguous duplicate keys (including escaped equivalents) and excessive
## nesting before the engine parser. Syntax validation remains the JSON parser's job.
static func _scan_json(text: String, source: String) -> Dictionary:
	var stack: Array = []
	var index := 0
	while index < text.length():
		var token := text[index]
		if token == '"':
			var start := index
			index += 1
			while index < text.length() and text[index] != '"':
				if text[index] == "\\":
					index += 1
				index += 1
			if index >= text.length():
				return failure("invalid_json", "$", source)
			var end := index
			var look := index + 1
			while look < text.length() and text[look] in [" ", "\t", "\r", "\n"]:
				look += 1
			if look < text.length() and text[look] == ":" and not stack.is_empty() and stack.back().object:
				var key_parser := JSON.new()
				if key_parser.parse(text.substr(start, end - start + 1)) != OK:
					return failure("invalid_json", "$", source)
				var key: String = key_parser.data
				if stack.back().keys.has(key):
					return failure("duplicate_json_key", key, source)
				stack.back().keys[key] = true
		elif token in ["{", "["]:
			stack.append({"object": token == "{", "keys": {}})
			if stack.size() > 32:
				return failure("json_depth_exceeded", "$", source)
		elif token in ["}", "]"]:
			if stack.is_empty():
				return failure("invalid_json", "$", source)
			stack.pop_back()
		index += 1
	return {"accepted": true}

static func parse_json(text: String, source: String = "") -> Dictionary:
	if text.to_utf8_buffer().size() > MAX_MANIFEST_BYTES:
		return failure("json_byte_budget_exceeded", "$", source)
	var scan := _scan_json(text, source)
	if not scan.accepted:
		return scan
	var parser := JSON.new()
	if parser.parse(text) != OK:
		return failure("invalid_json", "line:%d" % parser.get_error_line(), source)
	return {"accepted": true, "data": parser.data}

static func parse(text: String, source: String = "") -> Dictionary:
	var document := parse_json(text, source)
	if not document.accepted:
		return document
	var result := validate(document.data, source)
	if result.accepted:
		result["manifest_sha256"] = text.sha256_text()
	return result

static func validate(data: Variant, source: String = "") -> Dictionary:
	if not data is Dictionary:
		return failure("manifest_not_object", "$", source)
	var checked := _keys(data, ["schema", "pack_id", "version", "author", "license", "dependencies", "content"], "$", source)
	if not checked.accepted:
		return checked
	if not data.schema is String or data.schema != SCHEMA:
		return failure("unsupported_schema", "schema", source)
	if not valid_id(data.pack_id) or _reserved(data.pack_id):
		return failure("invalid_or_reserved_id", "pack_id", source)
	if not valid_version(data.version):
		return failure("invalid_version", "version", source)
	for field in ["author", "license"]:
		if not _text(data[field], 128):
			return failure("invalid_text", field, source)
	if not data.dependencies is Array or data.dependencies.size() > MAX_DEPENDENCIES:
		return failure("invalid_dependencies", "dependencies", source)
	var dependencies := {}
	for index in data.dependencies.size():
		var dependency = data.dependencies[index]
		var field := "dependencies[%d]" % index
		if not dependency is Dictionary:
			return failure("dependency_not_object", field, source)
		checked = _keys(dependency, ["pack_id", "version", "manifest_sha256"], field, source)
		if not checked.accepted:
			return checked
		if not valid_id(dependency.pack_id) or _reserved(dependency.pack_id) or dependency.pack_id == data.pack_id or dependencies.has(dependency.pack_id):
			return failure("invalid_dependency_id", field + ".pack_id", source)
		if not valid_version(dependency.version):
			return failure("invalid_version", field + ".version", source)
		if not valid_hash(dependency.manifest_sha256):
			return failure("invalid_hash", field + ".manifest_sha256", source)
		dependencies[dependency.pack_id] = true
	if not data.content is Array or data.content.is_empty() or data.content.size() > MAX_CONTENT:
		return failure("invalid_content", "content", source)
	var identities := {}
	for index in data.content.size():
		var entry = data.content[index]
		var field := "content[%d]" % index
		if not entry is Dictionary:
			return failure("content_not_object", field, source)
		checked = _keys(entry, ["id", "kind", "path", "sha256"], field, source)
		if not checked.accepted:
			return checked
		if not valid_id(entry.id) or entry.id.get_slice(":", 0) != data.pack_id.get_slice(":", 0) or identities.has(entry.id):
			return failure("invalid_or_duplicate_content_id", field + ".id", source)
		if entry.kind not in KINDS:
			return failure("unsupported_kind", field + ".kind", source)
		if not valid_path(entry.path):
			return failure("invalid_definition_path", field + ".path", source)
		if not valid_hash(entry.sha256):
			return failure("invalid_hash", field + ".sha256", source)
		identities[entry.id] = true
	return {"accepted": true, "reason": "manifest_valid", "field": "", "source": source, "manifest": data.duplicate(true)}
