extends RefCounted

## Internal frames are recursively immutable; all public exports duplicate them.
## Capture produces bounded, acyclic JSON-shaped values owned by this source.
static func freeze(value: Variant) -> void:
	if value is Dictionary:
		for child in value.values(): freeze(child)
		value.make_read_only()
	elif value is Array:
		for child in value: freeze(child)
		value.make_read_only()
