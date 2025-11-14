extends Resource
class_name AITuningConfig

## Global knobs for AI cadences and margins.

const DEFAULTS := {
	"decision_interval": 0.1,
	"danger_buffer": 0.5,
	"path_update_interval": 0.3
}

static func get_value(key: String, fallback = null):
	if DEFAULTS.has(key):
		return DEFAULTS[key]
	return fallback
