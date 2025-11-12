# Bomb Kick Feature

## Overview
The bomb kick ability allows players to kick bombs across the map, adding a strategic element to gameplay. This feature is inspired by Sega Saturn Bomberman.

## Gameplay Mechanics

### Obtaining the Ability
- Players must collect the **Bomb Kicker** power-up (7% drop rate from destroyed blocks)
- Once collected, the ability is active for the rest of the match
- The player's `has_bomb_kicker` flag is set to `true`

### Kicking Bombs
1. **Trigger**: When a player with the kick ability walks onto a tile containing a bomb
2. **Direction**: The bomb is kicked in the direction the player is moving
3. **Speed**: Kicked bombs slide at 200 pixels/second
4. **Visual Feedback**: Kicked bombs show:
   - Faster animation (2x speed)
   - Red tint (modulate color)

### Bomb Movement
- Kicked bombs slide continuously in the kick direction
- Bombs stop when they collide with:
  - Solid walls
  - Destructible blocks
  - Other bombs (both kicked and stationary)
  - Players
- Upon collision, bombs snap to the nearest grid center
- Bombs can trigger chain reactions when they collide with other bombs

### Stopping Kicked Bombs
- **Input**: Press the stop key (ESC/ui_cancel by default)
- **Range**: Player can stop any kicked bomb within a 3x3 tile area around them
- **Effect**: Bomb immediately stops and snaps to grid center
- **Use Case**: Allows precise bomb placement after kicking

## Technical Implementation

### Server-Side
- **ServerBomb**: Changed from `StaticBody2D` to `CharacterBody2D`
  - Supports physics-based movement via `move_and_collide()`
  - Tracks kick state: `is_kicked`, `kick_direction`, `kick_speed`
  - Collision mask includes walls, bombs, and players when kicked

- **ServerPlayer**: 
  - `try_kick_bomb_at_tile()`: Attempts to kick a bomb at specified tile
  - `request_stop_kicked_bomb()`: Requests to stop nearby kicked bombs

- **GameInstance**:
  - Physics process checks for kick conditions each frame
  - `get_bomb_at_tile()`: Helper to find bombs at specific positions
  - `stop_nearby_kicked_bombs()`: Stops kicked bombs in player's vicinity

### Network Synchronization
- Bomb state includes:
  - `is_kicked`: Boolean flag
  - `kick_direction`: Vector2 for movement direction
- State synced at 20Hz to all clients
- Client-side interpolation ensures smooth visual movement

### Client-Side
- **game_view.gd**: 
  - Captures stop_kicked_bomb input
  - Sends input to server
- **bomb_renderer.gd**:
  - `set_kicked_state()`: Updates visual feedback for kicked bombs
  - Applies animation speed and color modulation

## Balance Considerations
- Kick speed: 200 px/s (adjustable in `ServerBomb.kick_speed`)
- Power-up drop rate: 7% (configured in `GameInstance.spawn_powerup()`)
- Stop range: 3x3 tiles around player (Manhattan distance)

## Network Authority
- **Server-authoritative**: All bomb physics and collision detection occur on the server
- **Client prediction**: Not implemented for kicked bombs (server state is canonical)
- **Latency compensation**: Standard state interpolation ensures smooth visuals

## Future Enhancements
- [ ] Add particle effects for kicked bombs (dust trail)
- [ ] Sound effects for kicking and stopping
- [ ] Allow bombs to push players on collision
- [ ] Add "super kick" power-up for faster kick speed
- [ ] Implement bomb pass-through ability (walk through bombs without kicking)
