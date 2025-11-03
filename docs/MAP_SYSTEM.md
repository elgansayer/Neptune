# Dynamic Map System Documentation

## Overview

The Bomberman project now features a comprehensive dynamic map system that supports:

- **Procedural Generation**: Multiple algorithms for automatic map creation
- **File-Based Maps**: Load custom maps from JSON files
- **Multiple Map Styles**: Classic, Arena, Maze, Chaos, Wide, and Symmetric layouts
- **Spawn Point Management**: Automatic spawn point generation and validation
- **Map Validation**: Built-in validation for map quality

## Architecture

### Core Components

```
shared/maps/
├── map_generator.gd    # Procedural map generation with 6+ algorithms
├── map_loader.gd       # Load/save maps from JSON files
├── map_manager.gd      # Central map management API
├── map_test.gd         # Test scene for visualizing maps
└── map_test.tscn       # Test scene
```

### Map Data Structure

All maps use a common dictionary format:

```gdscript
{
    "grid": Array,              # 2D array of tile types [0=empty, 1=wall, 2=destructible]
    "spawn_points": Array,      # Array of Vector2 (world coordinates)
    "width": int,
    "height": int,
    "name": String,
    "style": String,            # Optional: "CLASSIC", "ARENA", etc.
    "metadata": Dictionary      # Optional: author, difficulty, theme, etc.
}
```

## Usage

### 1. Using MapManager (Recommended)

```gdscript
# Initialize
var map_manager = MapManager.new()
add_child(map_manager)

# Load from file
var map = map_manager.load_map(MapManager.MapSource.FILE, "res://res/maps/classic_arena.json")

# Generate procedural map
var map = map_manager.generate_procedural_map(MapGenerator.MapStyle.ARENA, 15, 13)

# Load random map file
var map = map_manager.load_random_map_file()

# Get spawn points
var spawn = map_manager.get_spawn_point(player_index)
var all_spawns = map_manager.get_all_spawn_points()

# Get map grid
var grid = map_manager.get_map_grid()
```

### 2. Direct Map Generation

```gdscript
# Create configuration
var config = MapGenerator.MapConfig.new(15, 13)
config.style = MapGenerator.MapStyle.CLASSIC
config.destructible_density = 0.6
config.seed_value = 12345  # Optional: reproducible maps

# Generate map
var map_data = MapGenerator.generate_map(config)
```

### 3. Loading Maps from Files

```gdscript
# Load specific map
var map_data = MapLoader.load_map_from_file("res://res/maps/classic_arena.json")

# List all available maps
var map_list = MapLoader.list_available_maps()

# Get map preview (metadata only, fast)
var preview = MapLoader.get_map_preview("res://res/maps/classic_arena.json")
# Returns: {name: String, metadata: Dictionary, spawn_count: int, size: Vector2i}

# Validate map
var validation = MapLoader.validate_map(map_data)
# Returns: {valid: bool, errors: Array, warnings: Array}
```

## Map Styles

### 1. CLASSIC
Traditional Bomberman grid pattern with:
- Regular grid of permanent walls (every other tile)
- Random destructible blocks
- 4 corner spawn points

**Best for**: 2-4 players, balanced gameplay

### 2. ARENA
Open center with walls around edges:
- Large open center area
- Destructible blocks in outer regions
- Strategic positioning emphasis

**Best for**: 4-6 players, fast-paced action

### 3. MAZE
Dense maze-like structure:
- Narrow winding corridors
- Multiple paths
- Generated using Prim's algorithm
- Strategic trap placement

**Best for**: 2-4 players, tactical gameplay

### 4. CHAOS
Completely random placement:
- No predictable patterns
- Random wall and block distribution
- Every game is unique

**Best for**: 2-6 players, unpredictable fun

### 5. WIDE
Large open spaces for many players:
- Sparse walls (every 3rd tile)
- Minimal destructible blocks
- Multiple spawn points

**Best for**: 6-10 players, battle royale

### 6. SYMMETRIC
Mirror-symmetric for competitive play:
- Perfect 4-way symmetry
- Fair starting positions
- Tournament-ready

**Best for**: 4 players, competitive matches

## Creating Custom Maps

### JSON File Format

Create a `.json` file in `res/maps/`:

```json
{
    "name": "My Custom Map",
    "author": "Your Name",
    "description": "Description of the map",
    "grid": [
        [1, 1, 1, 1, 1],
        [1, 0, 2, 0, 1],
        [1, 2, 1, 2, 1],
        [1, 0, 2, 0, 1],
        [1, 1, 1, 1, 1]
    ],
    "spawn_points": [
        {"x": 1, "y": 1},
        {"x": 3, "y": 3}
    ],
    "metadata": {
        "difficulty": "medium",
        "recommended_players": "2-4",
        "theme": "custom"
    }
}
```

### Tile Types

- `0` = Empty (walkable)
- `1` = Solid Wall (permanent, indestructible)
- `2` = Destructible Block (can be destroyed by bombs)

### Spawn Points

- Specified in **tile coordinates** (not world coordinates)
- Will be converted to world coordinates automatically
- Should be on empty tiles
- Automatically clears 3x3 area around spawn

## Integration with GameInstance

The `GameInstance` class now automatically uses the map system:

```gdscript
func _ready():
    # Map is loaded automatically
    # Choose one of these options:
    
    # Option 1: Load specific file
    map_data = map_manager.load_map(
        map_manager.MapSource.FILE, 
        "res://res/maps/classic_arena.json"
    )
    
    # Option 2: Random map file (default)
    map_data = map_manager.load_random_map_file()
    
    # Option 3: Generate procedural
    map_data = map_manager.generate_procedural_map(MapGenerator.MapStyle.ARENA)
```

Spawn points are now managed automatically:

```gdscript
func add_player(peer_id: int, username: String, spawn_position: Vector2 = Vector2.ZERO):
    # If no spawn position provided, uses next available spawn from map
    # Cycles through all spawn points automatically
```

## Included Maps

### 1. classic_arena.json
- **Size**: 15x13
- **Players**: 2-4
- **Style**: Traditional grid pattern
- **Difficulty**: Medium

### 2. open_battlefield.json
- **Size**: 15x13
- **Players**: 4-6
- **Style**: Open center arena
- **Difficulty**: Hard

### 3. narrow_passages.json
- **Size**: 15x13
- **Players**: 2-4
- **Style**: Maze-like corridors
- **Difficulty**: Expert

### 4. cross_roads.json
- **Size**: 15x15
- **Players**: 4
- **Style**: 4-way symmetric
- **Difficulty**: Medium
- **Features**: Competitive, tournament-ready

### 5. wide_battle_royale.json
- **Size**: 21x20
- **Players**: 6-10
- **Style**: Large open battlefield
- **Difficulty**: Medium

## Testing Maps

Run the map test scene to visualize and test all maps:

```bash
# From Godot Editor
# Open: res://shared/maps/map_test.tscn
# Press Play Scene (F6)

# Controls:
# SPACE - Cycle through all maps
# R - Reload/regenerate current map
# L - List all available maps
# V - Validate current map
# E - Export current map
# ESC - Quit
```

## Advanced Features

### Map Validation

```gdscript
var validation = MapLoader.validate_map(map_data)

if not validation.valid:
    print("Errors:", validation.errors)
    
if not validation.warnings.is_empty():
    print("Warnings:", validation.warnings)
```

Checks for:
- Minimum size requirements
- Spawn point presence and count
- Border walls
- Playable area connectivity
- Empty tile density

### Export Maps

```gdscript
# Export procedurally generated map to file
map_manager.export_current_map("user://my_generated_map.json")
```

### Reproducible Generation

```gdscript
# Use seed for identical maps
var config = MapGenerator.MapConfig.new()
config.seed_value = 42
config.style = MapGenerator.MapStyle.MAZE

var map1 = MapGenerator.generate_map(config)
var map2 = MapGenerator.generate_map(config)
# map1 and map2 will be identical
```

## Performance

- **Map Loading**: ~1-5ms for file-based maps
- **Map Generation**: 
  - Classic/Arena/Chaos: ~5-10ms
  - Maze: ~20-50ms (depends on size)
  - Wide: ~10-15ms
- **Collision Setup**: ~10-30ms (proportional to tile count)

## Best Practices

1. **For Competitive Play**: Use SYMMETRIC style or file-based symmetric maps
2. **For Casual Play**: Use CLASSIC or ARENA with random generation
3. **For Large Groups**: Use WIDE style or wide_battle_royale.json
4. **For Tournaments**: Create custom symmetric maps with exactly 4 spawns
5. **For Variety**: Use `load_random_map_file()` to keep games fresh

## Future Enhancements

Potential additions:
- [ ] Map editor GUI
- [ ] Power-up placement hints in map files
- [ ] Hazard tiles (lava, ice, etc.)
- [ ] Moving platforms
- [ ] Teleporters
- [ ] Map voting system for multiplayer
- [ ] Community map sharing
- [ ] Map difficulty rating system
- [ ] Progressive difficulty (shrinking map over time)
