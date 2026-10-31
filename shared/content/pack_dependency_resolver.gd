extends RefCounted

## Pure planning over already validated, locally registered manifest metadata.
## No file access, downloads, version ranges or latest-version fallback.
const Manifest = preload("res://shared/content/pack_manifest.gd")
const SCHEMA := "neptune.manifest-lock.v1"
const MAX_PACKS := 32

static func _identity(value: Variant, field: String, source: String = "") -> Dictionary:
	if not value is Dictionary:
		return Manifest.failure("identity_not_object", field, source)
	var keys := Manifest._keys(value, ["pack_id", "version", "manifest_sha256"], field, source)
	if not keys.accepted: return keys
	if not Manifest.valid_id(value.pack_id) or Manifest._reserved(value.pack_id):
		return Manifest.failure("invalid_pack_id", field + ".pack_id", source)
	if not Manifest.valid_version(value.version):
		return Manifest.failure("invalid_version", field + ".version", source)
	if not Manifest.valid_hash(value.manifest_sha256):
		return Manifest.failure("invalid_hash", field + ".manifest_sha256", source)
	return {"accepted": true}

static func _receipt(lock: Dictionary) -> Dictionary:
	var text := JSON.stringify(lock, "", true)
	return {"accepted": true, "reason": "manifest_lock_resolved", "lock": lock.duplicate(true),
		"lock_json": text, "lock_sha256": text.sha256_text()}

static func validate_lock(data: Variant, source: String = "") -> Dictionary:
	if not data is Dictionary:
		return Manifest.failure("lock_not_object", "$", source)
	var checked := Manifest._keys(data, ["schema", "roots", "packs"], "$", source)
	if not checked.accepted: return checked
	if not data.schema is String or data.schema != SCHEMA:
		return Manifest.failure("unsupported_lock_schema", "schema", source)
	var members := {}
	for field in ["roots", "packs"]:
		var values = data[field]
		if not values is Array or values.is_empty() or values.size() > MAX_PACKS:
			return Manifest.failure("invalid_lock_members", field, source)
		var previous := ""
		var identities := {}
		for index in values.size():
			var identity = values[index]
			checked = _identity(identity, "%s[%d]" % [field, index], source)
			if not checked.accepted: return checked
			if identity.pack_id <= previous:
				return Manifest.failure("noncanonical_or_duplicate_lock_member", "%s[%d]" % [field, index], source)
			previous = identity.pack_id
			identities[identity.pack_id] = identity
		members[field] = identities
	for id in members.roots:
		if not members.packs.has(id) or members.packs[id] != members.roots[id]:
			return Manifest.failure("lock_root_not_in_closure", "roots", source)
	return _receipt(data)

static func parse_lock(text: String, source: String = "") -> Dictionary:
	var parsed := Manifest.parse_json(text, source)
	if not parsed.accepted: return parsed
	return validate_lock(parsed.data, source)

static func _visit(catalogue: Dictionary, identity: Dictionary, state: Dictionary, source: String, field: String) -> Dictionary:
	var id: String = identity.pack_id
	if state.nodes.has(id) and state.nodes[id].identity.version != identity.version:
		return Manifest.failure("dependency_version_conflict", field + ".version", source)
	if state.visiting.get(id, false):
		var refusal := Manifest.failure("dependency_cycle", field, source)
		refusal["cycle"] = state.path.duplicate() + [id]
		return refusal
	var key: String = id + "@" + identity.version
	if not catalogue.has(key):
		return Manifest.failure("missing_dependency_release", field, source)
	state.constraints.append({"identity": identity, "source": source, "field": field})
	if state.nodes.has(id):
		return {"accepted": true}
	if state.nodes.size() >= MAX_PACKS:
		return Manifest.failure("dependency_closure_budget_exceeded", field, source)
	var record: Dictionary = catalogue[key]
	state.nodes[id] = record
	state.visiting[id] = true
	state.path.append(id)
	var dependencies := {}
	for index in record.manifest.dependencies.size():
		var dependency: Dictionary = record.manifest.dependencies[index]
		dependencies[dependency.pack_id] = {"identity": dependency, "field": "dependencies[%d]" % index}
	var ids: Array = dependencies.keys()
	ids.sort()
	for child in ids:
		var edge: Dictionary = dependencies[child]
		var result := _visit(catalogue, edge.identity, state, record.source, edge.field)
		if not result.accepted: return result
	state.path.pop_back()
	state.visiting[id] = false
	return {"accepted": true}

static func resolve(catalogue: Dictionary, roots: Array) -> Dictionary:
	# Incremental selection can combine up to 32 previous and 32 requested roots.
	if roots.is_empty() or roots.size() > MAX_PACKS * 2:
		return Manifest.failure("invalid_roots", "roots")
	var root_set := {}
	for index in roots.size():
		var identity = roots[index]
		var checked := _identity(identity, "roots[%d]" % index)
		if not checked.accepted: return checked
		if root_set.has(identity.pack_id) and root_set[identity.pack_id] != identity:
			return Manifest.failure("root_version_or_hash_conflict", "roots[%d]" % index)
		root_set[identity.pack_id] = identity.duplicate(true)
	if root_set.size() > MAX_PACKS:
		return Manifest.failure("root_budget_exceeded", "roots")
	var ids: Array = root_set.keys()
	ids.sort()
	var ordered_roots := []
	var state := {"nodes": {}, "visiting": {}, "path": [], "constraints": []}
	for id in ids:
		var identity: Dictionary = root_set[id]
		ordered_roots.append(identity.duplicate(true))
		var result := _visit(catalogue, identity, state, "", "roots:" + id)
		if not result.accepted: return result
	# Structural cycles are diagnosed before hash constraints. A real mutually
	# hash-pinned cycle would need cryptographic fixed points; malformed graph tests
	# must not invent verified cache identities to manufacture such a fixture.
	for request in state.constraints:
		var actual: Dictionary = state.nodes[request.identity.pack_id].identity
		if request.identity.manifest_sha256 != actual.manifest_sha256:
			return Manifest.failure("dependency_manifest_hash_mismatch", request.field + ".manifest_sha256", request.source)
	var closure := []
	var content_owners := {}
	ids = state.nodes.keys()
	ids.sort()
	for id in ids:
		var record: Dictionary = state.nodes[id]
		for entry in record.manifest.content:
			if content_owners.has(entry.id):
				return Manifest.failure("content_id_collision", "content.id:" + entry.id, record.source)
			content_owners[entry.id] = id
		closure.append(state.nodes[id].identity.duplicate(true))
	return _receipt({"schema": SCHEMA, "roots": ordered_roots, "packs": closure})
