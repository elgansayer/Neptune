extends RefCounted

## Public inventory and virus state determine average authoritative travel
## speed; planners must not assume the old five-tiles-per-second prototype.
static func tiles_per_second(player) -> float:
	if not is_instance_valid(player): return 0.0
	return GameConfig.BASE_SPEED / float(GameConfig.TILE_SIZE) \
		* GameConfig.get_skate_speed_multiplier(player.skate_count) \
		* player.get_virus_speed_modifier()
