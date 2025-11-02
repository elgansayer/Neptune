# SBomberman - Reference Implementation

## What is SBomberman?

SBomberman is a **previous Bomberman implementation** that serves as a reference for certain gameplay mechanics. It was built using a **client-authoritative peer-to-peer** architecture, which is fundamentally different from our current **server-authoritative** design.

## Key Differences

### SBomberman (Old)
- **Architecture**: Client-authoritative peer-to-peer
- **Networking**: Uses `rset()` for state synchronization between peers
- **Physics**: Uses Godot's `move_and_slide()` with built-in collision
- **Collision Exceptions**: Uses `add_collision_exception_with()` on client
- **Trust Model**: Relies on client honesty (can be cheated)

### Neptune-Bomberman (Current)
- **Architecture**: Server-authoritative with Godot headless server
- **Networking**: ENet RPC-based with state sync from server
- **Physics**: Server runs `move_and_slide()`, clients render state
- **Collision Exceptions**: Same API but server-side only
- **Trust Model**: Server is source of truth (cheat-proof)

## What We Can Learn From SBomberman

### ✅ Use These Patterns:
1. **Collision Exception System** - The pattern of using `add_collision_exception_with()` for bombs works great
2. **Corner Assistance/Wall Sliding** - The movement feel and cornering logic
3. **Tile-Based Grid System** - Grid positioning and alignment
4. **Explosion Propagation** - Multi-directional explosion with wall blocking

### ❌ Don't Copy These:
1. **Networking Code** - Uses peer-to-peer `rset()`, we use client-server RPCs
2. **Authority Model** - Clients make decisions, we let server decide everything
3. **State Management** - Each peer tracks its own state, we have single server state
4. **Trust Assumptions** - Assumes honest clients, we assume clients might cheat

## How to Use SBomberman

**As a Reference:**
- Look at movement feel and game mechanics
- Study the bomb placement and explosion logic
- Understand the player controls and responsiveness

**Not as a Blueprint:**
- Don't copy the networking architecture
- Don't use the same state management patterns
- Adapt mechanics to fit server-authoritative model

## Example: Bomb Collision

### SBomberman Pattern (Client-side):
```gdscript
# In bomb.gd
func _ready():
    player.add_collision_exception_with(self)  # Client decides

func _physics_process(delta):
    if player.grid_position != self.grid_position:
        player.remove_collision_exception_with(self)
```

### Neptune Pattern (Server-side):
```gdscript
# In server_player.gd
func place_bomb():
    var bomb = ServerBomb.new()
    bomb.add_collision_exception_with(self)  # Server decides
    collision_exceptions.append(bomb)

func _physics_process(delta):
    for bomb in collision_exceptions:
        if get_tile_position() != bomb.get_tile_position():
            bomb.remove_collision_exception_with(self)
```

Notice the **same API** but different **authority**: server decides, clients just see the result.

## Location

The SBomberman reference code is located at:
```
/home/elgan/bomberman/SBomberman/
```

Browse it for inspiration, but remember: **reference, not blueprint!**
