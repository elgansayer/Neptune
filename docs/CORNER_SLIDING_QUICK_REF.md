# Corner Sliding - Quick Reference

## What Was Implemented

**Bomberman-style "Assisted Cornering"** mechanic in `/home/elgan/bomberman/shared/entities/server_player.gd`

## How It Works (TL;DR)

```
Player presses RIGHT → Wall blocks → Game tries UP/DOWN → Player slides!
```

## The Logic

```gdscript
# 1. Get what player wants
desired_direction = input  # e.g., RIGHT

# 2. Check if that direction is clear
if clear(desired_direction):
    move(desired_direction)  # Normal movement
else:
    # 3. Try perpendicular directions
    if clear(UP):
        move(UP)  # Slide up around obstacle
    elif clear(DOWN):
        move(DOWN)  # Slide down around obstacle
    else:
        stop()  # Completely stuck
```

## Key Features

✅ **Automatic sliding** - Just hold one direction key  
✅ **Faces desired direction** - Character faces where you want to go, not where sliding  
✅ **No diagonal movement** - Strict 4-way (UP/DOWN/LEFT/RIGHT)  
✅ **Smooth navigation** - No getting stuck on corners  
✅ **Classic Bomberman feel** - Matches original game behavior  

## New Variables

| Variable | Type | Purpose |
|----------|------|---------|
| `desired_direction` | Vector2 | What the player is pressing |
| `current_movement_direction` | Vector2 | Actual movement (may differ due to sliding) |
| `COLLISION_CHECK_DISTANCE` | float | How far ahead to check (8 pixels) |

## New Functions

| Function | Purpose |
|----------|---------|
| `_check_direction_clear(direction)` | Tests if movement in direction would collide |
| `_get_perpendicular_directions(direction)` | Returns [UP, DOWN] or [LEFT, RIGHT] |
| `_setup_shape_casts()` | Creates collision checking nodes |

## Example Scenario

**Before:**
```
  ####
  #  #
  #  P  <- Player stuck, pressing RIGHT
  ####W  <- Wall blocking
```

**After (with corner sliding):**
```
  ####
  # P#  <- Player automatically moved UP
  #  #     (then will move RIGHT when clear)
  ####
```

## Testing

1. Create a map with single-tile walls
2. Position player next to a corner
3. Hold a direction key toward the corner
4. **Expected:** Player slides smoothly around corner

## Visual Comparison

### Without Corner Sliding ❌
```
Player input: →→→→→→
Player stuck: ⟼  (can't move)
```

### With Corner Sliding ✅
```
Player input: →→→→→→
Player moves: ↑↑→→→→  (automatically slides up, then right)
```

## Configuration

Adjust these values in `server_player.gd`:

```gdscript
const COLLISION_CHECK_DISTANCE = 8.0  # Increase for earlier detection
```

## Related Files

- **Implementation:** `/home/elgan/bomberman/shared/entities/server_player.gd`
- **Full Documentation:** `/home/elgan/bomberman/docs/CORNER_SLIDING.md`
- **Reference:** `/home/elgan/bomberman/SBomberman/players/player.gd`
- **Constants:** `/home/elgan/bomberman/shared/constants.gd`

## Debugging

Added to `get_state()`:
```gdscript
"desired_direction": {"x": ..., "y": ...}      # What player wants
"movement_direction": {"x": ..., "y": ...}     # Actual movement
```

Use these to verify sliding is working correctly.
