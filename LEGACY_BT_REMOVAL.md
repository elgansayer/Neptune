# Legacy Behavior Tree System Removal

## Summary
Completed migration from custom legacy behavior tree system to **LimboAI** plugin integration.

## Files Deleted

### Core AI Files
- `ai/bot_controller.gd` - Legacy bot controller (replaced by `server/ai/bot_controller.gd`)
- `ai/bot_manager.gd` - Legacy bot manager (replaced by `server/ai/bot_manager.gd`)
- `ai/tasks/` - Empty directory

### Legacy Behavior Tree System
- `shared/ai/behavior_tree/bt_runner.gd` - Custom BT tick scheduler
- `shared/ai/behavior_tree/nodes/base_node.gd` - Base BT node class
- `shared/ai/behavior_tree/nodes/selector.gd` - Legacy selector composite (renamed to LegacyBTSelector before deletion)
- `shared/ai/behavior_tree/nodes/sequence.gd` - Legacy sequence composite (renamed to LegacyBTSequence before deletion)
- `shared/ai/behavior_tree/nodes/utility_selector.gd` - Legacy utility selector (renamed to LegacyBTUtilitySelector before deletion)

### Legacy Leaf Nodes
- `shared/ai/behavior_tree/nodes/leaf_find_escape.gd` - BTEscapeNode
- `shared/ai/behavior_tree/nodes/leaf_move_to.gd` - BTMoveToNode
- `shared/ai/behavior_tree/nodes/leaf_chase_opponent.gd` - BTChaseOpponentNode
- `shared/ai/behavior_tree/nodes/leaf_place_bomb.gd` - BTPlaceBombNode
- `shared/ai/behavior_tree/nodes/leaf_collect_powerup.gd` - BTCollectPowerUpNode
- `shared/ai/behavior_tree/nodes/leaf_wait_ambush.gd` - BTWaitAmbushNode

## Code Changes

### `server/ai/bot_controller.gd`
**Removed:**
- Legacy BT const preloads (LegacyBTSequence, LegacyBTUtilitySelector, BTEscapeNode, etc.)
- `_bt_runner`, `_blackboard`, `_behavior_weights` class variables
- `_escape_sequence`, `_attack_sequence`, `_collect_sequence`, `_ambush_node` class variables
- `_build_behavior_tree()` function - built legacy BT structure
- `_update_blackboard()` function - updated legacy blackboard
- `_apply_outputs()` function - applied BT outputs to player
- `_score_behavior()` function - utility scoring for legacy BT
- `_limbo_active` references (undeclared variable)

**Updated:**
- `configure()` - removed USE_LIMBO_AI flag, now always uses LimboAI
- `_physics_process()` - simplified to only call `_tick_limbo()`, removed legacy BT pathway
- `get_debug_payload()` - simplified to only report LimboAI blackboard data

### `server/ai/bot_manager.gd`
**Updated:**
- `_BOT_CONTROLLER_PATHS` - changed from `["res://ai/bot_controller.gd"]` to `["res://server/ai/bot_controller.gd"]`

### `server/game_instance.gd`
**Updated:**
- `_BOT_MANAGER_PATHS` - removed fallback path `"res://ai/bot_manager.gd"`, kept only `"res://server/ai/bot_manager.gd"`

## Current AI System Architecture

### LimboAI Integration
The bot AI now uses **LimboAI** plugin exclusively:
- **BTPlayer** node manages tree execution
- **Blackboard** handles shared state between nodes
- **BehaviorTree** resource loaded from `server/ai/trees/bot_default.tres`

### Custom LimboAI Nodes
Located in `shared/ai/limbo_nodes/`:

**Conditions:**
- `bt_is_in_danger.gd` - Checks if bot is in blast radius
- `bt_has_opponent.gd` - Checks if opponent is available
- `bt_has_powerup_available.gd` - Checks if powerups exist on map
- `bt_is_cell_walkable.gd` - Validates movement targets
- `bt_has_client_input.gd` - Checks for buffered client input
- `bt_has_powerup.gd` - Checks if bot has specific powerup

**Actions:**
- `bt_find_escape_route.gd` - Calculates safe escape path using BFS
- `bt_move_to_cell.gd` - Moves bot towards target cell
- `bt_place_bomb.gd` - Places bomb with safety checks
- `bt_find_opponent.gd` - Locates nearest opponent
- `bt_find_powerup.gd` - Locates nearest powerup
- `bt_wait_ambush.gd` - Territorial control behavior
- `bt_update_input_from_buffer.gd` - Applies buffered client input
- `bt_process_power_glove.gd` - Handles power glove bomb manipulation

**Composites:**
- `bt_utility_selector.gd` - Custom utility-based priority selector

### Bot Behavior Tree Structure
4-branch priority tree in `server/ai/trees/bot_default.tres`:

1. **Escape Branch** (highest priority)
   - `BTIsInDanger` → `BTFindEscapeRoute` → `BTMoveToCell`
   
2. **Chase + Attack Branch**
   - `BTHasOpponent` → `BTFindOpponent` → `BTMoveToCell` → `BTPlaceBomb`
   
3. **Collect Powerup Branch**
   - `BTHasPowerupAvailable` → `BTFindPowerup` → `BTMoveToCell`
   
4. **Ambush Branch** (lowest priority)
   - `BTWaitAmbush` (territorial control)

### Supporting AI Systems (Retained)
These systems work with LimboAI custom nodes:
- `GridSampler` - Tile-based pathfinding and spatial queries
- `HazardPredictor` - Explosion prediction and danger zones
- `OpponentTracker` - Opponent position tracking
- `BombPlanner` - Bomb placement strategy
- `BombSafetyChecker` - Time-aware BFS suicide prevention
- `OpeningGambit` - Deterministic opening strategy
- `UtilityScorer` - Mathematical decision-making
- `AIManager` - Centralized AI brain with ThreatMatrix

## Benefits of LimboAI Migration

1. **Visual Editor**: Behavior trees are editable in Godot Editor via LimboAI panel
2. **Native Integration**: Uses Godot 4.x native classes (BTSelector, BTSequence, BTPlayer)
3. **Better Debugging**: LimboAI provides built-in tree visualization and breakpoints
4. **Cleaner Architecture**: Separation of concerns - nodes handle specific tasks
5. **Extensibility**: Easy to add new custom nodes by extending `BTAction`, `BTCondition`, `BTComposite`
6. **Performance**: Optimized C++ core with GDScript bindings

## Migration Notes

- All bot AI logic remains server-authoritative
- Client prediction system unchanged
- AI personalities config (`shared/ai/config/personalities.gd`) retained
- Opening gambit state machine retained in `bot_controller.gd`
- Utility scoring system retained but could be integrated into custom BTUtilitySelector in future

## Testing Recommendations

1. Verify bots spawn correctly in dedicated server
2. Test all 4 behavior branches (escape, chase, collect, ambush)
3. Validate opening gambit execution
4. Check bot debug payload streaming to clients
5. Test with multiple AI personalities (BALANCED, AGGRESSIVE, DEFENSIVE, TACTICAL)

## Future Improvements

- Migrate utility scoring into BTUtilitySelector custom composite
- Add LimboAI decorators (cooldowns, random chance, repeat)
- Implement LimboAI state machine for opening gambit
- Add runtime tree hot-reloading for AI tuning during matches
