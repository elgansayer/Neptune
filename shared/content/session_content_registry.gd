extends RefCounted

## An in-memory catalogue and explicitly selected exact-pinned dependency closure.
## No downloads, resource mounting, version ranges or filesystem installation.
const Manifest = preload("res://shared/content/pack_manifest.gd")
const Dependencies = preload("res://shared/content/pack_dependency_resolver.gd")
const MAX_RELEASES := 128
const MAX_SELECTED := 32
var _catalogue := {}
var _selected := {}
var _content := {}
var _roots: Array = []
var _lock := {}

func register_manifest(text: String, source: String = "") -> Dictionary:
	var parsed := Manifest.parse(text, source)
	if not parsed.accepted:
		return parsed
	var manifest: Dictionary = parsed.manifest
	var key: String = manifest.pack_id + "@" + manifest.version
	var identity := {"pack_id": manifest.pack_id, "version": manifest.version, "manifest_sha256": parsed.manifest_sha256}
	if _catalogue.has(key):
		if _catalogue[key].identity != identity:
			return Manifest.failure("immutable_version_conflict", "version", source)
		return {"accepted": true, "reason": "already_registered", "identity": identity.duplicate(true)}
	if _catalogue.size() >= MAX_RELEASES:
		return Manifest.failure("release_budget_exceeded", "pack_id", source)
	_catalogue[key] = {"manifest": manifest, "identity": identity, "source": source}
	return {"accepted": true, "reason": "registered", "identity": identity.duplicate(true)}

func select_pack(pack_id: String, version: String, manifest_sha256: String) -> Dictionary:
	return select_roots([{"pack_id": pack_id, "version": version, "manifest_sha256": manifest_sha256}])

func resolve_roots(roots: Array) -> Dictionary:
	return Dependencies.resolve(_catalogue, roots)

func select_roots(roots: Array, expected_lock: Dictionary = {}) -> Dictionary:
	var requested: Array = _roots.duplicate(true)
	requested.append_array(roots)
	var plan := resolve_roots(requested)
	if not plan.accepted: return plan
	if not expected_lock.is_empty():
		var checked := Dependencies.validate_lock(expected_lock)
		if not checked.accepted: return checked
		if checked.lock != plan.lock:
			return Manifest.failure("manifest_lock_mismatch", "lock")
	var selected := {}
	var content := {}
	for identity in plan.lock.packs:
		if _selected.has(identity.pack_id) and _selected[identity.pack_id] != identity:
			return Manifest.failure("selected_version_conflict", "version")
		var key: String = identity.pack_id + "@" + identity.version
		var record: Dictionary = _catalogue[key]
		for entry in record.manifest.content:
			if content.has(entry.id):
				return Manifest.failure("content_id_collision", "content.id:" + entry.id, record.source)
			var descriptor: Dictionary = identity.duplicate(true)
			descriptor.merge({"content_id": entry.id, "kind": entry.kind, "sha256": entry.sha256})
			content[entry.id] = {"entry": entry.duplicate(true), "descriptor": descriptor, "source": record.source}
		selected[identity.pack_id] = identity.duplicate(true)
	# Commit the complete graph only after every identity, edge and collision passed.
	_selected = selected
	_content = content
	_roots = plan.lock.roots.duplicate(true)
	_lock = plan.lock.duplicate(true)
	return plan.duplicate(true)

func apply_lock(text: String, source: String = "") -> Dictionary:
	var parsed := Dependencies.parse_lock(text, source)
	if not parsed.accepted: return parsed
	var result := select_roots(parsed.lock.roots, parsed.lock)
	if not result.accepted and result.get("source", "").is_empty(): result["source"] = source
	return result

func session_lock() -> Dictionary:
	return _lock.duplicate(true)

func resolve(content_id: String) -> Dictionary:
	if not _content.has(content_id):
		return Manifest.failure("unknown_content", "content_id")
	var result: Dictionary = _content[content_id].duplicate(true)
	result.merge({"accepted": true, "reason": "content_resolved"})
	return result

func inventory() -> Array:
	var result := []
	var keys: Array = _catalogue.keys()
	keys.sort()
	for key in keys:
		result.append(_catalogue[key].identity.duplicate(true))
	return result

func selection() -> Array:
	var result := []
	var keys: Array = _selected.keys()
	keys.sort()
	for key in keys:
		result.append(_selected[key].duplicate(true))
	return result
