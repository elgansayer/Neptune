extends RefCounted

## Read-only public-state preparation for the same trajectory used by the
## authority. A candidate never grants permission after the world changes.
const Trajectory = preload("res://shared/throw_trajectory.gd")
const Forecast = preload("res://shared/ai/perception/bomb_threat_forecast.gd")
const Safety = preload("res://shared/ai/planning/bomb_safety_checker.gd")
const Movement = preload("res://shared/ai/movement_timing.gd")
const INVALID_TARGET := Vector2i(-999, -999)

class PublicContext extends Node:
	var bombs: Dictionary
	var players: Dictionary
	var active_explosion_tiles: Dictionary

class ForecastManager extends RefCounted:
	var _game_instance: Node
	var sampler
	func simulate_threat_matrix(cell: Vector2i, radius: int, now: float, fuse: float) -> Dictionary:
		return Forecast.build(_game_instance, sampler, now,
			{"cell": cell, "range": radius, "fuse_lower_bound": fuse, "elapsed": 0.0})

static func choose(player, world, sampler, target: Vector2i = INVALID_TARGET,
		preferred: Vector2 = Vector2.ZERO, require_target: bool = true) -> Dictionary:
	var failure := {"supported": false, "reason": "unavailable"}
	if not is_instance_valid(player) or world == null or sampler == null or not player.has_power_glove:
		return failure
	var candidate := _candidate(player, world)
	if candidate.is_empty(): return {"supported": false, "reason": "no_normal_throwable_bomb"}
	if int(candidate.kind) != ServerBomb.BOMB_TYPE_NORMAL:
		return {"supported": false, "reason": "unsupported_throw_bomb_type"}
	var speed := Movement.tiles_per_second(player)
	if not is_finite(speed) or speed <= 0.0: return failure
	var arena := PublicContext.new()
	arena.bombs = world.bombs.duplicate()
	arena.bombs.erase(candidate.id)
	arena.players = world.players.duplicate()
	arena.active_explosion_tiles = world.active_explosion_tiles.duplicate()
	var now: float = world.get_simulation_time_msec()
	var timeline := Forecast.build_timeline(arena, sampler, now)
	var manager := ForecastManager.new()
	manager._game_instance = arena
	manager.sampler = sampler
	var checker := Safety.new()
	checker.configure(manager, sampler)
	# If a new placement cannot be picked up, the ordinary survival branch
	# still needs a real grounded escape; no failed search becomes permission.
	if not player.is_carrying_bomb() and not checker.can_safely_plant_bomb(
			player.get_tile_position(), player.get_tile_position(), candidate.radius,
			speed, now, candidate.remaining_fuse, player):
		arena.free()
		return {"supported": false, "reason": "no_failed_pickup_escape"}
	var best := {"supported": false, "reason": "no_safe_targeted_trajectory", "score": -INF}
	var directions: Array[Vector2] = [Vector2.RIGHT, Vector2.LEFT, Vector2.DOWN, Vector2.UP]
	if preferred != Vector2.ZERO:
		if not preferred.is_finite() or preferred not in directions:
			arena.free()
			return failure
		directions = [preferred]
	for direction: Vector2 in directions:
		var evaluated := _evaluate(player, world, sampler, target, direction,
			candidate, timeline, checker, speed, now, require_target)
		if evaluated.get("supported", false) and evaluated.score > best.score:
			best = evaluated
	arena.free()
	return best

static func _candidate(player, world) -> Dictionary:
	var own_id := ""
	if player.is_carrying_bomb():
		if not player.has_method("public_data"): return {}
		own_id = str(player.public_data().get("carried_bomb_id", ""))
	for id in world.bombs:
		var bomb = world.bombs[id]
		if not is_instance_valid(bomb) or bomb.has_exploded: continue
		var matches: bool = str(id) == own_id if not own_id.is_empty() else bomb.get_tile_position() == player.get_tile_position() and bomb.bomb_state == ServerBomb.BombState.PLANTED
		if matches:
			var observation: Dictionary = bomb.get_forecast_observation()
			return {"id": str(id), "kind": int(observation.get("bomb_type", 0)),
				"radius": int(observation.range), "fuse": float(observation.fuse_lower_bound),
				"remaining_fuse": maxf(0.0, float(observation.fuse_lower_bound) - float(observation.elapsed)),
				"position": bomb.position}
	if not own_id.is_empty() or not player.can_place_bomb(): return {}
	return {"id": "", "kind": player.bomb_type, "radius": player.get_effective_bomb_range(),
		"fuse": player.get_bomb_fuse_lower_bound(), "remaining_fuse": player.get_bomb_fuse_lower_bound(),
		"position": player.position}

static func _blocked(cell: Vector2i, world, subject_id: String) -> bool:
	if world.get_tile_type(cell) != 0: return true
	for actor in world.players.values():
		if is_instance_valid(actor) and not actor.is_dead and actor.get_tile_position() == cell: return true
	for id in world.bombs:
		var bomb = world.bombs[id]
		if str(id) != subject_id and is_instance_valid(bomb) and not bomb.has_exploded and bomb.get_tile_position() == cell: return true
	return false

static func _evaluate(player, world, sampler, target: Vector2i, direction: Vector2,
		candidate: Dictionary, timeline: Dictionary, checker, speed: float,
		now: float, require_target: bool) -> Dictionary:
	var failure := {"supported": false}
	if player.last_move_direction != direction and not _facing_window_safe(player, sampler, timeline, now):
		return failure
	var dimensions := Vector2i(GameConfig.map_width, GameConfig.map_height)
	var route: Dictionary = Trajectory.plan(player.get_tile_position(), direction, dimensions,
		GameConfig.TILE_SIZE, func(cell: Vector2i) -> bool: return _blocked(cell, world, candidate.id))
	if not route.complete or route.waypoints.is_empty(): return failure
	var points: Array[Vector2] = route.waypoints
	var origin := Trajectory.center(player.get_tile_position(), GameConfig.TILE_SIZE)
	var flight: Dictionary = Trajectory.describe_flight(candidate.position, origin, candidate.position,
		points.back(), points.front(), 0.0, 0, points, dimensions, GameConfig.TILE_SIZE,
		ServerBomb.THROW_DURATION, maxf(Engine.time_scale, 1.0) / Engine.physics_ticks_per_second)
	if not flight.complete or flight.landing_cells.size() > 8: return failure
	var until := now + float(flight.maximum_remaining_msec) + 100.0
	for raw in flight.trajectory_cells:
		var cell := Vector2i(int(raw[0]), int(raw[1]))
		if not sampler.is_in_bounds(cell) or not Forecast.is_window_safe(timeline.intervals, cell, now, until): return failure
	# Keep real emergency preemption: recovery may only run while unrelated
	# public hazards permit its actual preparation/flight window.
	if not Forecast.is_window_safe(timeline.intervals, player.get_tile_position(), now, until): return failure
	for raw in flight.landing_cells:
		var cell := Vector2i(int(raw[0]), int(raw[1]))
		if not sampler.is_in_bounds(cell): return failure
		var blast: Array[Vector2i] = Forecast.project(cell, candidate.radius, sampler)
		if require_target and not blast.has(target): return failure
		if not checker.can_safely_plant_bomb(player.get_tile_position(), cell, candidate.radius,
			speed, now, float(candidate.fuse) + float(flight.minimum_remaining_msec) / 1000.0, player): return failure
	return {"supported": true, "reason": "public_shared_trajectory", "direction": direction,
		"waypoints": points, "flight": flight, "bomb_id": candidate.id,
		"landing_tile": Vector2i(floori(points.back().x / GameConfig.TILE_SIZE), floori(points.back().y / GameConfig.TILE_SIZE)),
		"score": 10.0 - points.size() * 0.1}

static func _facing_window_safe(player, sampler, timeline: Dictionary, now: float) -> bool:
	# Facing is a real motor step: corner assist or grid alignment can move
	# sideways as well. Cover the entire next-frame body footprint, including
	# the public maximum accumulator step; never assume it turns in place.
	var frame_sec := maxf(Engine.time_scale, 1.0) / Engine.physics_ticks_per_second
	var step: float = GameConfig.SATURN_MAX_PIXELS_PER_FRAME * GameConfig.scale_factor * 60.0 \
		* player.get_virus_speed_modifier() * frame_sec
	var radius: float = GameConfig.PLAYER_HALF_WIDTH + step + GameConfig.SNAP_TO_CENTER_SPEED * frame_sec
	var low := Vector2i(floori((player.position.x - radius) / GameConfig.TILE_SIZE),
		floori((player.position.y - radius) / GameConfig.TILE_SIZE))
	var high := Vector2i(floori((player.position.x + radius) / GameConfig.TILE_SIZE),
		floori((player.position.y + radius) / GameConfig.TILE_SIZE))
	for y in range(low.y, high.y + 1):
		for x in range(low.x, high.x + 1):
			var cell := Vector2i(x, y)
			if not sampler.is_in_bounds(cell) or not Forecast.is_window_safe(timeline.intervals,
					cell, now, now + frame_sec * 1000.0 + 100.0): return false
	return true
