extends RefCounted

## One global-arena visibility contract. Only JSON-safe values cross this API.
const MAX_CELLS := 65536
const MAX_ENTITIES := 1024
const PLAYER_FIELDS := ["player_id", "username", "is_bot", "is_dead", "is_spectator", "bombs_placed", "max_bombs", "bomb_range", "skate_count", "speed_multiplier", "has_bomb_kicker", "has_power_glove", "has_line_bomb", "has_full_fire", "bomb_type", "active_virus", "is_mounted", "tirra_growth_level", "is_flying", "is_immortal", "carried_bomb_id"]

static func xy(position: Vector2) -> Array:
	return [position.x, position.y]

static func facing(name: String) -> Array:
	return {"UP": [0, -1], "DOWN": [0, 1], "LEFT": [-1, 0], "RIGHT": [1, 0]}.get(name, [0, 1])

static func capture(game: Node) -> Dictionary:
	var out := {"schema": 1, "valid": true, "bot_supported": true, "unsupported": [],
		"tile_size": GameConfig.TILE_SIZE, "tick": game.simulation_tick,
		"server_time": game.get_simulation_time_msec(), "active": game.match_active,
		"terrain": [], "players": {}, "bombs": {}, "powerups": {}, "eggs": {}, "mounts": {}, "projectiles": {}, "flames": {}}
	var count: int = game.players.size() + game.bombs.size() + game.powerups.size() + game.eggs.size() + game.tirras.size()
	var cells := 0
	for row in game.game_map:
		cells += row.size()
	var width: int = game.game_map[0].size() if not game.game_map.is_empty() else 0
	var rectangular := width > 0
	for row in game.game_map:
		if row.size() != width:
			rectangular = false
	if not rectangular or cells > MAX_CELLS or count > MAX_ENTITIES or game.game_map.is_empty():
		out.valid = false
		out.bot_supported = false
		out.unsupported = ["observation_budget_or_empty_map"]
		return out
	out.terrain = game.game_map.duplicate(true)
	for row in out.terrain:
		for tile in row:
			if tile not in [0, 1, 2, 3] and "terrain" not in out.unsupported:
				out.unsupported.append("terrain")
	for peer_id in game.players:
		var actor = game.players[peer_id]
		if not is_instance_valid(actor) or actor.is_queued_for_deletion():
			continue
		var state: Dictionary = actor.get_state()
		var data := {"peer_id": peer_id, "kind": "player", "position": xy(actor.position), "velocity": xy(actor.velocity), "facing": facing(state.facing)}
		for field in PLAYER_FIELDS:
			if state.has(field):
				data[field] = state[field]
		data["fuse_lower_bound"] = actor.get_bomb_fuse_lower_bound()
		data["effective_range"] = actor.get_effective_bomb_range()
		data["virus_speed_modifier"] = actor.get_virus_speed_modifier()
		data["placement_disabled"] = actor.active_virus == ServerPlayer.VirusType.CONSTIPATION
		data["collision_layer"] = actor.collision_layer
		data["collision_mask"] = actor.collision_mask
		out.players[str(peer_id)] = data
	for id in game.bombs:
		var bomb = game.bombs[id]
		if not is_instance_valid(bomb) or bomb.is_queued_for_deletion():
			continue
		var state: Dictionary = bomb.get_state()
		if not state.is_visible:
			continue
		var exemptions: Array = []
		for body in bomb.get_collision_exceptions():
			if is_instance_valid(body) and body is ServerPlayer and game.players.get(body.peer_id) == body:
				exemptions.append(body.peer_id)
		var data := {"kind": "bomb", "bomb_id": str(id), "owner_id": state.owner_id,
			"position": xy(bomb.position), "velocity": xy(bomb.velocity), "range": state.range,
			"state": state.state, "carrier_id": state.carrier_id,
			"fuse_lower_bound": state.fuse_lower_bound, "fuse_upper_bound": state.fuse_upper_bound, "elapsed": state.timer,
			"exploded": bomb.has_exploded, "kick_direction": xy(bomb.kick_direction),
			"collision_layer": bomb.collision_layer, "overlap_exemptions": exemptions,
			"bomb_type": bomb.bomb_type, "blast_cells": state.blast_cells, "flight": state.flight}
		out.bombs[str(id)] = data
		if bomb.bomb_state == ServerBomb.BombState.THROWN:
			out.projectiles[str(id)] = {"kind": "bomb_projectile", "id": str(id), "position": data.position.duplicate(), "collision_layer": bomb.collision_layer}
		if bomb.bomb_type not in [0, 1, 2, 3] and "bomb_type" not in out.unsupported:
			out.unsupported.append("bomb_type")
	for id in game.powerups:
		var item = game.powerups[id]
		if not is_instance_valid(item) or item.is_queued_for_deletion() or item.collected or item.destroyed or not item.visible or not _exposed(out, item.position):
			continue
		out.powerups[str(id)] = {"kind": "powerup", "id": str(id), "position": xy(item.position), "powerup_type": item.powerup_type}
	for id in game.eggs:
		var egg = game.eggs[id]
		if is_instance_valid(egg) and egg.visible and _exposed(out, egg.position):
			out.eggs[str(id)] = {"kind": "egg", "id": str(id), "position": xy(egg.position)}
	for id in game.tirras:
		var mount = game.tirras[id]
		if is_instance_valid(mount) and mount.visible and _exposed(out, mount.position):
			out.mounts[str(id)] = {"kind": "mount", "id": str(id), "position": xy(mount.position)}
	for key in game.active_explosion_tiles:
		if game.active_explosion_tiles[key] >= out.server_time:
			out.flames[key] = game.active_explosion_tiles[key]
	out.bot_supported = out.unsupported.is_empty()
	return out

static func _exposed(snapshot: Dictionary, position: Vector2) -> bool:
	if not position.is_finite():
		return false
	var tile := Vector2i(floor(position.x / snapshot.tile_size), floor(position.y / snapshot.tile_size))
	return tile.y >= 0 and tile.y < snapshot.terrain.size() and tile.x >= 0 and tile.x < snapshot.terrain[tile.y].size() and snapshot.terrain[tile.y][tile.x] == 0
