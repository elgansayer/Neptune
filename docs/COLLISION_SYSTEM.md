# Collision Layer System

## Overview

The Bomberman game uses Godot's physics layer system to allow players to pass through each other while still colliding with walls and bombs. This creates the classic Bomberman gameplay feel.

## Layer Configuration

### Collision Layers (defined in `shared/constants.gd`)

```gdscript
const COLLISION_LAYER_WALLS = 1      # Layer 1 (bit 0): Solid/destructible walls
const COLLISION_LAYER_PLAYERS = 2    # Layer 2 (bit 1): Player characters
const COLLISION_LAYER_BOMBS = 4      # Layer 3 (bit 2): Bombs
const COLLISION_LAYER_EXPLOSIONS = 8 # Layer 4 (bit 3): Explosion damage areas
```

### How Layers Work in Godot

- `collision_layer`: Which layer(s) THIS body is on (what it "is")
- `collision_mask`: Which layer(s) THIS body can collide with (what it "sees")

### Entity Configurations

#### Walls (StaticBody2D)
- **Layer**: 1 (COLLISION_LAYER_WALLS)
- **Mask**: 0 (walls don't need to detect anything)
- **Collides with**: Nothing (they are obstacles, not detectors)

**Code**: `server/game_instance.gd` in `_create_map_collision()`
```gdscript
tile_body.collision_layer = Constants.COLLISION_LAYER_WALLS
tile_body.collision_mask = 0
```

#### Players (CharacterBody2D)
- **Layer**: 2 (COLLISION_LAYER_PLAYERS)
- **Mask**: 5 (COLLISION_LAYER_WALLS | COLLISION_LAYER_BOMBS = 1 | 4 = 5)
- **Collides with**: Walls and bombs, but NOT other players

**Code**: `shared/entities/server_player.gd` in `_ready()`
```gdscript
collision_layer = Constants.COLLISION_LAYER_PLAYERS
collision_mask = Constants.COLLISION_LAYER_WALLS | Constants.COLLISION_LAYER_BOMBS
```

#### Bombs (StaticBody2D)
- **Layer**: 4 (COLLISION_LAYER_BOMBS)
- **Mask**: 1 (COLLISION_LAYER_WALLS)
- **Collides with**: Walls only (not players or other bombs)

**Code**: `shared/entities/server_bomb.gd` in `_ready()`
```gdscript
collision_layer = Constants.COLLISION_LAYER_BOMBS
collision_mask = Constants.COLLISION_LAYER_WALLS
```

## Collision Matrix

|           | Walls | Players | Bombs | Explosions |
|-----------|-------|---------|-------|------------|
| **Walls**     | -     | ✓       | ✓     | ✓          |
| **Players**   | ✓     | ✗       | ✓     | ✓          |
| **Bombs**     | ✓     | ✗       | ✗     | -          |
| **Explosions**| ✓     | ✓       | -     | -          |

- ✓ = Can collide
- ✗ = Cannot collide
- \- = Not applicable/not implemented yet

## Special Cases

### Bomb Placement Exception

When a player places a bomb, they need to be able to walk out of it (otherwise they'd be trapped). This is handled by:

1. Adding a collision exception for the bomb to the player
2. The exception allows the player to pass through their own bomb temporarily
3. Once the player leaves the bomb tile, they can collide with it again

**Code**: `server/game_instance.gd` in `place_bomb()`
```gdscript
player.add_bomb_collision_exception(bomb)
```

### ShapeCast Configuration

The player uses `ShapeCast2D` nodes for corner sliding detection. These must match the player's collision mask:

```gdscript
shape_cast.collision_mask = Constants.COLLISION_LAYER_WALLS | Constants.COLLISION_LAYER_BOMBS
```

This ensures corner sliding detection only considers walls and bombs, not other players.

## Benefits

1. **Player Pass-Through**: Players can walk through each other, reducing frustration in tight spaces
2. **Classic Bomberman Feel**: Matches the original game's physics
3. **Bomb Collision**: Players are blocked by bombs (except their own when placing)
4. **Performance**: Efficient collision detection with minimal checks

## Testing

To verify the collision system:

1. Start the server: `./bomberman-cli.py server --quick-start`
2. Connect two clients
3. Try walking players through each other (should pass through)
4. Try walking into walls (should be blocked)
5. Place a bomb and walk away, then try to walk back (should be blocked)

## Future Enhancements

- **Explosion Layer**: Add collision layer for explosion damage detection
- **Power-up Layer**: Add layer for collectible items
- **Kickable Bombs**: May need to adjust bomb collision when kick power-up is active
