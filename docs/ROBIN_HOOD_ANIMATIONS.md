# Robin Hood Character Animation System

## Overview
The game now uses the complete Robin Hood character sprite from `player-robin-hood.pck` with full animation support for all 34 animations.

## Animation Categories

### 1. Directional Animations (24 animations)
Each direction (East, North, South, West) has multiple state animations:

#### East (6 animations)
- `east_stopped` - Standing still facing right
- `east_walk` - Walking right (3 frames)
- `east_carry` - Carrying bomb while walking right (3 frames)
- `east_hold` - Holding bomb while standing right (1 frame)
- `east_jump` - Jumping right (1 frame)
- `east_ride` - Riding mount right (1 frame)

#### North (8 animations)
- `north_stopped` - Standing still facing up
- `north_walk` - Walking up (3 frames)
- `north_carry` - Carrying bomb while walking up (3 frames)
- `north_hold` - Holding bomb while standing up (1 frame)
- `north_jump` - Jumping up (1 frame)
- `north_ride` - Riding mount up (1 frame)
- `north_ride_loss` - Losing on mount up (1 frame)
- `north_ride_win` - Winning on mount up (1 frame)

#### South (6 animations)
- `south_stopped` - Standing still facing down
- `south_walk` - Walking down (3 frames)
- `south_carry` - Carrying bomb while walking down (3 frames)
- `south_hold` - Holding bomb while standing down (1 frame)
- `south_jump` - Jumping down (1 frame)
- `south_ride` - Riding mount down (1 frame)

#### West (6 animations)
- `west_stopped` - Standing still facing left
- `west_walk` - Walking left (3 frames)
- `west_carry` - Carrying bomb while walking left (3 frames)
- `west_hold` - Holding bomb while standing left (1 frame)
- `west_jump` - Jumping left (1 frame)
- `west_ride` - Riding mount left (1 frame)

### 2. State Animations (6 animations)
Global state animations that override directional animations:

- `state_defeat` - Death animation (9 frames) - **Priority 1**
- `state_stunned` - Stunned/dizzy (4 frames) - **Priority 2**
- `state_panic` - Panicking near explosion (3 frames) - **Priority 3**
- `state_win` - Victory pose (4 frames)
- `state_lose` - Loss pose (3 frames)
- `state_idle` - Generic idle (8 frames) - **Fallback only**

### 3. HUD Animations (2 animations)
Portrait animations for UI:

- `hud_idle` - Player portrait idle (1 frame)
- `hud_lose` - Player portrait losing (1 frame)

## Animation Priority System

The animation system uses a priority hierarchy to determine which animation to play:

1. **Death** (`state_defeat`) - Highest priority
   - Triggered when: `is_alive == false`
   
2. **Stunned** (`state_stunned`)
   - Triggered when: `is_stunned == true`
   
3. **Panic** (`state_panic`)
   - Triggered when: `is_panicking == true` (near explosion)
   
4. **Carrying/Holding Bomb** (`{direction}_carry` or `{direction}_hold`)
   - Triggered when: `is_carrying_bomb == true`
   - Uses `_carry` if moving, `_hold` if stopped
   
5. **Walking** (`{direction}_walk`)
   - Triggered when: `velocity >= 10.0`
   - Direction determined by `facing` server data
   
6. **Stopped** (`{direction}_stopped`) - Lowest priority
   - Triggered when: `velocity < 10.0`
   - Maintains last facing direction

## Direction Mapping

Server sends facing direction as strings, mapped to animation prefixes:

| Server Facing | Animation Prefix |
|--------------|------------------|
| `RIGHT`      | `east`           |
| `DOWN`       | `south`          |
| `LEFT`       | `west`           |
| `UP`         | `north`          |

## Implementation Details

### Location
All animation logic is in `/client/game_view.gd` in the `update_player()` function (lines ~277-330).

### Key Features
1. **Direction Persistence**: Last facing direction is stored in player node metadata
2. **Safe Animation Loading**: Checks if animation exists before playing
3. **Fallback System**: Falls back to `state_idle` if requested animation missing
4. **State Detection**: Checks server data for game states (alive, stunned, carrying, etc.)

### Future Server States
The system is prepared for future server-side features:
- `is_alive` - Player death detection
- `is_stunned` - Stun state (future feature)
- `is_panicking` - Panic near explosions (future feature)
- `is_carrying_bomb` - Bomb carrying/kicking (future feature)

## Testing

To verify animations are working:
```bash
# Run game and watch animation changes
./bomberman-cli.py both

# List all available animations
godot --headless --script /tmp/test_animations.gd --path /home/elgan/bomberman
```

## Current Status

✅ **Working Animations:**
- All directional stopped animations (north/south/east/west_stopped)
- All directional walk animations (north/south/east/west_walk)
- Smooth transitions between animations
- Direction persistence when stopped

⏳ **Future Animations** (waiting for server implementation):
- Carry/hold animations (need bomb carrying state)
- Jump animations (need jump mechanic)
- Ride animations (need mount system)
- Defeat animation (need death state)
- Panic animation (need danger proximity detection)
- Stunned animation (need stun mechanic)

## Notes

- The animation system is fully prepared for all 34 animations
- State animations will automatically activate when server implements the corresponding features
- No animation shows missing errors - all 34 animations confirmed present in PCK
- System gracefully falls back to `state_idle` if an expected animation is missing
