extends RefCounted

## An in-memory catalogue and explicitly selected session set; no downloads,
## resource mounting, dependency solver or filesystem installation is performed.
const Manifest = preload("res://shared/content/pack_manifest.gd")
const MAX_RELEASES := 128
const MAX_SELECTED := 32
var _catalogue := {}
var _selected := {}
var _content := {}

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
	var key := pack_id + "@" + version
	if not _catalogue.has(key):
		return Manifest.failure("unknown_release", "pack_id")
	var record: Dictionary = _catalogue[key]
	if record.identity.manifest_sha256 != manifest_sha256:
		return Manifest.failure("manifest_hash_mismatch", "manifest_sha256", record.source)
	if _selected.has(pack_id):
		if _selected[pack_id] == record.identity:
			return {"accepted": true, "reason": "already_selected"}
		return Manifest.failure("selected_version_conflict", "version", record.source)
	if _selected.size() >= MAX_SELECTED:
		return Manifest.failure("selection_budget_exceeded", "pack_id", record.source)
	# Declarations are validated now; resolution is deliberately the next contract.
	if not record.manifest.dependencies.is_empty():
		return Manifest.failure("dependency_selection_not_supported", "dependencies", record.source)
	for entry in record.manifest.content:
		if _content.has(entry.id):
			return Manifest.failure("content_id_collision", "content.id:" + entry.id, record.source)
	# Commit the entire addition only after every registration has passed.
	for entry in record.manifest.content:
		var descriptor: Dictionary = record.identity.duplicate(true)
		descriptor.merge({"content_id": entry.id, "kind": entry.kind, "sha256": entry.sha256})
		_content[entry.id] = {"entry": entry.duplicate(true), "descriptor": descriptor, "source": record.source}
	_selected[pack_id] = record.identity.duplicate(true)
	return {"accepted": true, "reason": "selected"}

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
