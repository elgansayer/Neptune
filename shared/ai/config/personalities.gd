extends Resource
class_name AIPersonalitiesConfig

## Stores behavior weights derived from docs/AI_PERSONALITIES_REFERENCE.md.

const BASE_PROFILE := {
	"decision_interval": 0.08,  # Balanced reaction time
	"escape_bias": 2.0,  # High priority on escaping but not paralyzing
	"attack_bias": 1.2,  # Encourage attacking
	"powerup_bias": 0.8,
	"ambush_bias": 0.3,
	"danger_buffer": 1.5,  # Reasonable time to escape
	"escape_radius": 8,  # Standard search radius
	"ambush_window": 0.75,
	"path_depth": 40,
	"aggression": 0.6  # More proactive
}

const PROFILES := {
	"BALANCED": {},
	"AGGRESSIVE": {
		"decision_interval": 0.06,
		"escape_bias": 2.5,  # Even aggressive bots need to survive
		"attack_bias": 1.5,
		"powerup_bias": 0.5,
		"danger_buffer": 1.5,  # Still need time to escape
		"ambush_bias": 0.05,
		"aggression": 0.9
	},
	"DEFENSIVE": {
		"decision_interval": 0.05,
		"escape_bias": 4.0,  # Maximum survival priority
		"attack_bias": 0.5,
		"powerup_bias": 1.2,
		"danger_buffer": 2.5,  # Extra cautious
		"ambush_window": 1.2,
		"escape_radius": 12,
		"aggression": 0.2
	}
}

static func get_profile(name: String) -> Dictionary:
	var profile := BASE_PROFILE.duplicate(true)
	var override: Dictionary = PROFILES.get(name, PROFILES["BALANCED"])
	for key in override.keys():
		profile[key] = override[key]
	return profile
