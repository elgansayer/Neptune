# Dynamic Map System - Quick Reference

## 🚀 Quick Start

```gdscript
# 1. Initialize MapManager
var map_manager = MapManager.new()
add_child(map_manager)

# 2. Load a map (choose one)
var map = map_manager.load_random_map_file()  # Random from files
# OR
var map = map_manager.load_map(MapManager.MapSource.FILE, "res://res/maps/classic_arena.json")
# OR
var map = map_manager.generate_procedural_map(MapGenerator.MapStyle.ARENA)

# 3. Use the map
var grid = map_manager.get_map_grid()
var spawn = map_manager.get_spawn_point(player_index)
```

## 📦 Map Styles (Procedural Generation)

| Style | Best For | Players | Characteristics |
|-------|----------|---------|-----------------|
| `CLASSIC` | Balanced play | 2-4 | Traditional grid pattern |
| `ARENA` | Fast action | 4-6 | Open center, strategic walls |
| `MAZE` | Tactical | 2-4 | Narrow corridors, complex paths |
| `CHAOS` | Unpredictable | 2-6 | Random placement |
| `WIDE` | Battle royale | 6-10 | Large open spaces |
| `SYMMETRIC` | Competitive | 4 | Perfect 4-way symmetry |

## 🗺️ Included Maps

1. **classic_arena.json** - 15x13, 4 players, medium difficulty
2. **open_battlefield.json** - 15x13, 4-6 players, hard
3. **narrow_passages.json** - 15x13, 2-4 players, expert
4. **cross_roads.json** - 15x15, 4 players, symmetric
5. **wide_battle_royale.json** - 21x20, 6-10 players, large scale

## 🔧 Common Tasks

### Generate Reproducible Map
```gdscript
var config = MapGenerator.MapConfig.new(15, 13)
config.seed_value = 12345
config.style = MapGenerator.MapStyle.CLASSIC
var map = MapGenerator.generate_map(config)
```

### Validate Map
```gdscript
var validation = map_manager.validate_current_map()
if not validation.valid:
    print("Errors:", validation.errors)
```

### List Available Maps
```gdscript
var maps = map_manager.list_all_maps()
for map_info in maps:
    print(map_info.name, " - ", map_info.spawn_count, " spawns")
```

### Export Generated Map
```gdscript
map_manager.export_current_map("user://my_map.json")
```

## 📝 JSON Map Format

```json
{
    "name": "My Map",
    "grid": [
        [1, 1, 1, 1, 1],
        [1, 0, 2, 0, 1],
        [1, 1, 1, 1, 1]
    ],
    "spawn_points": [
        {"x": 1, "y": 1},
        {"x": 3, "y": 1}
    ],
    "metadata": {
        "difficulty": "medium",
        "recommended_players": "2-4"
    }
}
```

**Tile Types:** `0` = Empty | `1` = Wall | `2` = Destructible

## 🎮 Test Scene

Open `res://shared/maps/map_test.tscn` and press F6

**Controls:**
- `SPACE` - Next map
- `R` - Reload/regenerate
- `V` - Validate
- `E` - Export
- `L` - List maps
- `ESC` - Quit

## 🔗 Files

- `shared/maps/map_generator.gd` - Procedural generation
- `shared/maps/map_loader.gd` - File loading/saving
- `shared/maps/map_manager.gd` - Unified API
- `res/maps/*.json` - Map files
- `docs/MAP_SYSTEM.md` - Full documentation

## ⚡ Performance

- File load: ~1-5ms
- Generation: 5-50ms (depends on style)
- Maze generation: slowest (~20-50ms)

## 💡 Tips

1. Use `SYMMETRIC` for tournaments
2. Use `load_random_map_file()` for variety
3. Set `seed_value` for reproducible testing
4. Validate custom maps before using
5. Keep 3x3 spawn zones clear of blocks
