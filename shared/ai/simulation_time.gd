extends RefCounted

## Bot decisions use their authority's physics clock, never host uptime.
static func milliseconds(blackboard) -> float:
	var game = blackboard.get_var("game_instance")
	if not is_instance_valid(game):
		push_error("Bot decision has no authoritative simulation clock")
		return 0.0
	return game.get_simulation_time_msec()

static func seconds(blackboard) -> float:
	return milliseconds(blackboard) / 1000.0
