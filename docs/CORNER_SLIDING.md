# Bomberman-Style Corner Sliding (Assisted Cornering)

## Overview

This document describes the "Assisted Cornering" or "Collision Sliding" mechanic implemented in `server_player.gd`. This is a classic Bomberman feature that prevents players from getting stuck on corners when navigating the grid-based map.

## The Problem

In grid-based games like Bomberman, players often get stuck on single-tile-thick corners when trying to navigate around obstacles. For example:

```
  ####
  #  #
  #  X  <- Player trying to move RIGHT
  ####P  <- But the wall blocks them
```

Without assisted cornering, the player would be completely stuck even though there's a clear path just slightly above or below them.

## The Solution

The assisted cornering mechanic automatically tries perpendicular directions when the desired direction is blocked:

1. **Player presses RIGHT** (desired direction)
2. **Game checks RIGHT** → Blocked by wall
3. **Game checks UP** (perpendicular 1) → Clear!
4. **Player moves UP** automatically
5. Once clear of the wall, player continues moving RIGHT

## Implementation Details

### Core Logic Flow

The movement logic in `_physics_process()` follows this sequence:

```gdscript
# Step A: Get desired direction from input
desired_direction = get_4way_input()

# Step B: Check if desired direction is clear
if _check_direction_clear(desired_direction):
    final_direction = desired_direction  # Normal case
else:
    # Step C: Desired direction blocked - check perpendiculars
    perpendiculars = _get_perpendicular_directions(desired_direction)
    
    if _check_direction_clear(perpendiculars[0]):
        final_direction = perpendiculars[0]  # Slide in first perpendicular
    elif _check_direction_clear(perpendiculars[1]):
        final_direction = perpendiculars[1]  # Slide in second perpendicular
    else:
        final_direction = Vector2.ZERO  # Completely stuck
        
# Step D: Apply movement
velocity = final_direction * speed
move_and_slide()
```

### Key Functions

#### `_check_direction_clear(direction: Vector2) -> bool`
Uses `PhysicsTestMotionParameters2D` to check if movement in a given direction would collide with obstacles. This is a "look-ahead" test that doesn't actually move the player.

#### `_get_perpendicular_directions(direction: Vector2) -> Array`
Returns the two perpendicular cardinal directions for any given direction:
- **Horizontal input** (LEFT/RIGHT) → Returns [UP, DOWN]
- **Vertical input** (UP/DOWN) → Returns [LEFT, RIGHT]

### Facing Direction vs Movement Direction

An important detail: the player's **facing direction** is based on the **desired direction** (what they're pressing), not the actual movement direction:

```gdscript
# Update facing based on DESIRED direction (what player wants)
if abs(desired_direction.y) > abs(desired_direction.x):
    facing_direction = "UP" if desired_direction.y < 0 else "DOWN"
else:
    facing_direction = "LEFT" if desired_direction.x < 0 else "RIGHT"
```

This means if you're holding RIGHT but sliding UP around a corner, your character still faces RIGHT (showing your intent), which feels natural to players.

## Example Scenario

### Scenario: Navigating Around a Corner

**Initial State:**
```
  ####
  #  #
  #  P  <- Player at (5, 5), holding RIGHT
  ####W  <- Wall at (6, 5)
```

**Frame 1:**
- Input: RIGHT
- `desired_direction = Vector2.RIGHT`
- Check RIGHT → **BLOCKED** by wall
- Check UP → **CLEAR**
- `final_direction = Vector2.UP`
- Player moves UP to (5, 4)
- Player faces RIGHT (desired direction)

**Frame 2:**
```
  ####
  # P#  <- Player at (5, 4), still holding RIGHT
  #  #
  ####
```

- Input: RIGHT
- `desired_direction = Vector2.RIGHT`
- Check RIGHT → **CLEAR** (past the corner!)
- `final_direction = Vector2.RIGHT`
- Player moves RIGHT to (6, 4)
- Player faces RIGHT

**Result:** The player smoothly navigated around the corner by just holding RIGHT, without needing to press UP manually.

## Collision Detection Details

### PhysicsTestMotionParameters2D

The collision checking uses Godot's built-in physics test motion:

```gdscript
var test_params = PhysicsTestMotionParameters2D.new()
test_params.from = global_transform
test_params.motion = direction.normalized() * COLLISION_CHECK_DISTANCE
test_params.exclude_bodies = collision_exceptions  # Don't collide with our own bombs

var result = PhysicsTestMotionResult2D.new()
var collision_detected = PhysicsServer2D.body_test_motion(get_rid(), test_params, result)
```

This checks if the player **would** collide if they moved a small distance (8 pixels) in the given direction, without actually moving them.

### Collision Exceptions

The `collision_exceptions` array contains bombs the player has just placed. This allows them to walk out of the bomb tile before the collision is re-enabled.

## Benefits

1. **Smooth Navigation:** Players can hold a single direction key and smoothly navigate corners
2. **Reduced Frustration:** No getting stuck on single-tile corners
3. **Competitive Gameplay:** Allows fast, fluid movement essential for competitive play
4. **Classic Feel:** Matches the feel of classic Bomberman games

## Comparison to SBomberman

The SBomberman reference implementation (`SBomberman/players/player.gd`) uses a similar approach but with some differences:

### SBomberman Approach:
- Uses `move_and_slide()` with Godot's built-in sliding
- Relies more on the physics engine's natural wall sliding
- Has additional complexity for network synchronization (peer-to-peer)

### Our Approach:
- Explicit perpendicular direction checking before movement
- Server-authoritative (client-server architecture)
- Uses `PhysicsTestMotionParameters2D` for look-ahead collision detection
- Clearer separation between desired direction and actual movement

## Testing the Mechanic

To test corner sliding:

1. Create a map with single-tile-wide walls
2. Position your player next to a corner
3. Hold a single direction key (e.g., RIGHT) toward the corner
4. Observe that the player automatically slides around the corner without additional input

### Expected Behavior:
- ✅ Player slides smoothly around corners
- ✅ Player faces the direction they're pressing (not the slide direction)
- ✅ Player moves in desired direction once the path is clear
- ✅ Player stops if completely surrounded (all 4 directions blocked)

### Common Issues:
- ❌ Player gets stuck on corners → Check `COLLISION_CHECK_DISTANCE` value
- ❌ Player doesn't slide → Verify `_check_direction_clear()` is working
- ❌ Player slides too aggressively → Adjust collision shapes or check distance

## Future Enhancements

Potential improvements to consider:

1. **Adaptive Sliding:** Prioritize the perpendicular direction that's "closer" to being aligned with the desired direction
2. **Slide Damping:** Slightly reduce speed when sliding vs normal movement
3. **Visual Feedback:** Show a subtle indicator when sliding is active
4. **Corner Snap:** When very close to clearing a corner, snap to the aligned position

## References

- SBomberman Implementation: `/home/elgan/bomberman/SBomberman/players/player.gd`
- Constants: `/home/elgan/bomberman/shared/constants.gd`
- Game Architecture: `/home/elgan/bomberman/ARCHITECTURE.md`
