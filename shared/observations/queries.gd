extends RefCounted

static func tile_of(position: Array, tile_size: float) -> Vector2i:
	return Vector2i(int(floor(float(position[0]) / tile_size)), int(floor(float(position[1]) / tile_size)))

static func terrain_at(snapshot: Dictionary, tile: Vector2i) -> int:
	var map: Array = snapshot.get("terrain", [])
	if tile.y < 0 or tile.y >= map.size() or tile.x < 0 or tile.x >= map[tile.y].size():
		return 1
	return int(map[tile.y][tile.x])

static func at_cell(snapshot: Dictionary, tile: Vector2i, for_peer: int = 0) -> Array[Dictionary]:
	var found: Array[Dictionary] = []
	var terrain := terrain_at(snapshot, tile)
	if terrain != 0:
		found.append({"kind": "terrain", "type": terrain, "blocking": true})
	var subject: Dictionary = snapshot.get("players", {}).get(str(for_peer), {})
	var mask: int = int(subject.get("collision_mask", 5))
	for group in ["players", "bombs", "powerups", "eggs", "mounts", "projectiles"]:
		for id in snapshot.get(group, {}):
			var data: Dictionary = snapshot[group][id]
			if tile_of(data.position, snapshot.tile_size) != tile:
				continue
			var blocking := false
			if group == "players":
				blocking = data.peer_id != for_peer and (int(data.collision_layer) & mask) != 0
			elif group == "bombs":
				blocking = not data.exploded and data.state not in [ServerBomb.BombState.CARRIED, ServerBomb.BombState.THROWN] and (int(data.collision_layer) & mask) != 0 and for_peer not in data.overlap_exemptions
			found.append({"kind": data.kind, "id": id, "blocking": blocking})
	return found
