extends Resource
class_name AIPersonalitiesConfig

## Stores behavior weights derived from docs/AI_PERSONALITIES_REFERENCE.md.

const BASE_PROFILE := {
	"decision_interval": 0.1,
	"escape_bias": 1.2,
	"attack_bias": 1.0,
	"powerup_bias": 0.8,
	"ambush_bias": 0.2,
	"danger_buffer": 1.25,
	"escape_radius": 8,
	"ambush_window": 0.75,
	"path_depth": 40,
	"aggression": 0.5
}

const PROFILES := {
	"BALANCED": {},
	"AGGRESSIVE": {
		"decision_interval": 0.08,
		"attack_bias": 1.5,
		"powerup_bias": 0.5,
		"danger_buffer": 0.8,
		"ambush_bias": 0.05,
		"aggression": 0.9
	},
	"DEFENSIVE": {
		"decision_interval": 0.12,
		"escape_bias": 1.8,
		"attack_bias": 0.6,
		"powerup_bias": 1.1,
		"danger_buffer": 1.8,
		"ambush_window": 1.2,
		"aggression": 0.2
	}
}

static func get_profile(name: String) -> Dictionary:
	var profile := BASE_PROFILE.duplicate(true)
	var override: Dictionary = PROFILES.get(name, PROFILES["BALANCED"])
	for key in override.keys():
		profile[key] = override[key]
	return profile
