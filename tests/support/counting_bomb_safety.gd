extends RefCounted

var delegate
var calls := 0

func check_plant_safety_detailed(bot: Vector2i, plant: Vector2i, radius: int,
		speed: float, now: float, allow_dead_end: bool = false, fuse: float = 3.0, actor: Node = null) -> Dictionary:
	calls += 1
	return delegate.check_plant_safety_detailed(bot, plant, radius, speed, now, allow_dead_end, fuse, actor)
