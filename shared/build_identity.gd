extends RefCounted
class_name NeptuneBuildIdentity

const Revision = preload("res://shared/build_revision.gd")

static func revision() -> String:
	return Revision.REVISION

static func compact() -> String:
	return revision().left(12)

static func is_release() -> bool:
	return revision().length() == 40 and revision().is_valid_hex_number(false)
