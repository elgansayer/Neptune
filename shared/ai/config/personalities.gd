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
	},
	"TIMID": {
		"decision_interval": 0.08,
		"escape_bias": 2.0,
		"attack_bias": 0.1,
		"powerup_bias": 0.9,
		"ambush_bias": 0.05,
		"danger_buffer": 2.0,
		"escape_radius": 10,
		"aggression": 0.1
	},
	"GREEDY": {
		"decision_interval": 0.03,
		"escape_bias": 1.0,
		"attack_bias": 0.3,
		"powerup_bias": 1.5,
		"ambush_bias": 0.0,
		"danger_buffer": 1.0,
		"path_depth": 50,
		"aggression": 0.3
	},
	"CHAOS": {
		"decision_interval": 0.01,
		"escape_bias": 0.6,
		"attack_bias": 1.8,
		"powerup_bias": 0.4,
		"ambush_bias": 0.1,
		"danger_buffer": 0.6,
		"escape_radius": 5,
		"aggression": 0.9
	},
	"KAMIKAZE": {
		"decision_interval": 0.005,
		"escape_bias": 0.2,
		"attack_bias": 2.5,
		"powerup_bias": 0.3,
		"ambush_bias": 0.0,
		"danger_buffer": 0.2,
		"escape_radius": 3,
		"aggression": 1.5
	},
	"STRATEGIC": {
		"decision_interval": 0.04,
		"escape_bias": 1.2,
		"attack_bias": 1.2,
		"powerup_bias": 1.0,
		"ambush_bias": 0.3,
		"danger_buffer": 1.2,
		"path_depth": 50,
		"aggression": 0.6
	},
	"TRAPPER": {
		"decision_interval": 0.06,
		"escape_bias": 0.9,
		"attack_bias": 1.0,
		"powerup_bias": 0.6,
		"ambush_bias": 1.8,
		"danger_buffer": 0.9,
		"ambush_window": 1.5,
		"aggression": 0.5
	}
}

static func get_profile(name: String) -> Dictionary:
	var profile := BASE_PROFILE.duplicate(true)
	var override: Dictionary = PROFILES.get(name, PROFILES["BALANCED"])
	for key in override.keys():
		profile[key] = override[key]
	return profile
