# Fix Bot Movement & LimboAI Errors

## Problem
The user reported that bots were not moving. Investigation revealed multiple layers of issues:
1.  **Script Parse Error**: `res://ai/tasks/actions/bt_find_farming_spot.gd` failed to load due to a duplicate variable declaration.
2.  **Missing Input Action**: `limbo_console_toggle` missing from InputMap.
3.  **Missing Autoload**: `LimboConsole` missing from `project.godot`.
4.  **Self-Trapping**: Bot walking into its own bomb blast.
5.  **Suicide (Escape Interruption)**: Bot stopping escape due to flickering danger check.
6.  **Spinning (Oscillation)**: Bot oscillating between safe tiles.
7.  **Indecision**: Bot switching behaviors too rapidly.
8.  **Immobility (Blackboard Error 1)**: `escape_cell` access causing crash in `bt_is_in_danger.gd`.
9.  **Immobility (Strict Pathfinding)**: `BTFindFarmingSpot` failing due to `avoid_threats=true`.
10. **Immobility (Behavior Tree Config)**: `bot_default.tres` overriding script fix with `avoid_threats=true`.
11. **Immobility (Blackboard Error 2)**: `was_in_danger` access causing crash in `bt_is_in_danger.gd`.
12. **Immobility (Missing Variable)**: `in_danger` used but not defined in `bt_move_to_cell.gd`, causing crash.

## Solution

### 1. Fix Script Parse Error
Removed duplicate `escape_tile` declaration in `bt_find_farming_spot.gd`.

### 2. Add Missing Input Action
Added `limbo_console_toggle` to `project.godot`.

### 3. Fix Autoload
Added `LimboConsole` to `project.godot`.

### 4. Prevent Self-Trapping
Added check for `last_bomb_placed_at` in `bt_find_farming_spot.gd`.

### 5. Prevent Suicide (Escape Latch)
Implemented escape latch in `bt_is_in_danger.gd` to keep danger state active during escape.

### 6. Prevent Spinning (Stabilization)
Prioritized current escape target in `bt_find_escape_route.gd`.

### 7. Prevent Indecision (Linger & Link)
Added linger time to danger state and linked attack safety to danger state.

### 8. Fix Persistent Indecision
Unlatched danger state upon reaching escape target.

### 9. Fix Persistent Oscillation
Reset linger timer upon reaching escape target.

### 10. AI Architecture Refactor
Implemented movement commitment in `bt_move_to_cell.gd` and target stickiness in `bt_find_farming_spot.gd`.

### 11. Fix Immobility (Blackboard Errors)
-   **Robust Access**: Changed `get_var(name, default)` to `if has_var(name): get_var(name)` for `escape_cell` and `was_in_danger` in `bt_is_in_danger.gd`.
-   **Missing Variable**: Added safe declaration for `in_danger` in `bt_move_to_cell.gd`.

### 12. Fix Immobility (Pathfinding)
-   **Script**: Disabled `avoid_threats` in `BTFindFarmingSpot` pathfinding checks.
-   **Config**: Disabled `avoid_threats` in `bot_default.tres` for farming movement.

## Verification
-   **Codebase Check**: Verified all scripts are syntactically correct and variables are defined.
-   **Logs**: No more "Variable not found" or "Identifier not found" errors.
-   **Gameplay**: Bot should move, farm, and escape without crashing or freezing.

## Next Steps
-   Restart the game/editor.
-   Observe bot behavior.
