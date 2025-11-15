# LimboAI Behavior Tree Examples for Neptune-Bomberman

This document provides concrete examples of Behavior Trees for different entity types in the game.

## Table of Contents

1. [Bot AI Behavior Trees](#bot-ai-behavior-trees)
2. [Player Controller Behavior Tree](#player-controller-behavior-tree)
3. [Bomb Lifecycle Behavior Tree](#bomb-lifecycle-behavior-tree)
4. [Advanced Patterns](#advanced-patterns)

---

## Bot AI Behavior Trees

### 1. Aggressive Bot

**Goal**: Prioritizes attacking opponents, only escapes when in immediate danger.

```
Root: BTSelector (Utility-weighted)
│
├─── [Priority: CRITICAL] Escape Sequence
│    ├─── BTIsInDanger (check_immediate=true)
│    ├─── BTFindEscapeRoute (escape_radius=8)
│    └─── BTMoveToCell
│
├─── [Priority: HIGH] Attack Sequence
│    ├─── BTIsOpponentNearby (max_distance=5)
│    ├─── BTFindAttackPosition
│    ├─── BTMoveToCell
│    └─── BTPlaceBomb
│
├─── [Priority: MEDIUM] Collect Powerup Sequence
│    ├─── BTIsPowerupAvailable (max_distance=6)
│    ├─── BTFindNearestPowerup
│    └─── BTMoveToCell
│
└─── [Priority: LOW] Patrol/Wait
     └─── BTWanderRandom
```

**Blackboard Variables**:
- `player` - ServerPlayer reference
- `game_instance` - GameInstance reference
- `hazard_predictor` - HazardPredictor reference
- `opponent_tracker` - OpponentTracker reference
- `target_cell` - Vector2i (set by find actions)
- `personality` - Dictionary with weights

**File**: `res://shared/ai/limbo_trees/bot_aggressive.tres`

### 2. Defensive Bot

**Goal**: Prioritizes survival, attacks only when safe.

```
Root: BTSelector
│
├─── [Priority: CRITICAL] Escape Sequence
│    ├─── BTIsInDanger (danger_buffer=1.5)
│    ├─── BTFindEscapeRoute (escape_radius=10)
│    └─── BTMoveToCell
│
├─── [Priority: HIGH] Collect Powerup Sequence
│    ├─── BTIsPowerupAvailable (max_distance=8)
│    ├─── BTIsPowerupSafe  # Custom condition
│    ├─── BTFindNearestPowerup
│    └─── BTMoveToCell
│
├─── [Priority: MEDIUM] Safe Attack Sequence
│    ├─── BTIsOpponentNearby (max_distance=3)
│    ├─── BTIsSafeToPlaceBomb  # Check if we can escape after placing
│    ├─── BTFindAttackPosition
│    ├─── BTMoveToCell
│    └─── BTPlaceBomb
│
└─── [Priority: LOW] Hide/Wait
     └─── BTFindSafePosition
```

**File**: `res://shared/ai/limbo_trees/bot_defensive.tres`

### 3. Balanced Bot

**Goal**: Balanced approach between offense and defense.

```
Root: BTSelector (Utility-weighted)
│
├─── [Weight: 2.0] Escape Sequence
│    ├─── BTIsInDanger (danger_buffer=1.0)
│    ├─── BTFindEscapeRoute (escape_radius=8)
│    └─── BTMoveToCell
│
├─── [Weight: 1.5] Attack Sequence
│    ├─── BTIsOpponentNearby (max_distance=4)
│    ├─── BTCanEscapeAfterBomb  # Safety check
│    ├─── BTFindAttackPosition
│    ├─── BTMoveToCell
│    └─── BTPlaceBomb
│
├─── [Weight: 0.8] Collect Powerup Sequence
│    ├─── BTIsPowerupAvailable (max_distance=7)
│    ├─── BTFindNearestPowerup
│    └─── BTMoveToCell
│
└─── [Weight: 0.2] Ambush/Wait
     └─── BTWaitAmbush
```

**File**: `res://shared/ai/limbo_trees/bot_balanced.tres`

---

## Player Controller Behavior Tree

**Goal**: Process client inputs on the server using BT logic.

```
Root: BTSequence (Always executes every frame)
│
├─── BTUpdateInputFromBuffer (peek_only=true)
│    # Reads latest input and sets movement
│
└─── BTSelector (Action Processing)
     │
     ├─── Power Glove Branch
     │    └─── BTSequence
     │         ├─── BTHasPowerup (type=POWER_GLOVE)
     │         ├─── BTHasClientInput (input="action_pressed")
     │         └─── BTProcessPowerGlove
     │              # Handles: Throw -> Pickup -> Place
     │
     └─── Standard Branch
          └─── BTSequence
               ├─── BTHasClientInput (input="place_bomb")
               ├─── BTCanPlaceBomb
               └─── BTPlaceBomb
```

**Blackboard Variables**:
- `player` - ServerPlayer reference
- `game_instance` - GameInstance reference
- `input_buffer` - InputBuffer reference
- `input_x`, `input_y` - Movement input
- `action_pressed`, `action_released` - Action button state
- `place_bomb` - Bomb placement request

**Key Difference from AI Bots**:
- Player BT reads from `input_buffer` instead of making autonomous decisions
- No utility scoring needed (inputs are deterministic)
- Simpler structure (input processing, not AI)

**File**: `res://shared/ai/limbo_trees/player_controller.tres`

---

## Bomb Lifecycle Behavior Tree

**Goal**: Manage bomb's tick-to-explode lifecycle using BT.

### Simple Version

```
Root: BTSequence
│
├─── BTCheckFuseExpired
│    # Condition: explosion_timer >= FUSE_TIME
│
└─── BTExplodeBomb
     # Action: Call bomb.explode()
```

**File**: `res://shared/ai/limbo_trees/bomb_simple.tres`

### Advanced Version (with kick handling)

```
Root: BTSelector
│
├─── Kicked Bomb Sequence
│    └─── BTSequence
│         ├─── BTIsKicked
│         ├─── BTUpdateKickedMovement
│         └─── BTCheckKickedCollision
│
└─── Normal Fuse Sequence
     └─── BTSequence
          ├─── BTCheckFuseExpired
          └─── BTExplodeBomb
```

**Blackboard Variables**:
- `bomb` - ServerBomb reference
- `current_time` - Current game time
- `game_instance` - For collision checks

**File**: `res://shared/ai/limbo_trees/bomb_advanced.tres`

---

## Advanced Patterns

### 1. Utility-Based Selector

For dynamic priority based on game state:

```gdscript
# Custom node: BTUtilitySelector
@tool
extends BTComposite
class_name BTUtilitySelector

## Selects child based on utility score
## Each child should have a score_function or weight

func _tick(delta: float) -> int:
    # Calculate utility score for each child
    var scored_children = []
    
    for child in get_children():
        var score = _calculate_score(child)
        scored_children.append({"child": child, "score": score})
    
    # Sort by score (highest first)
    scored_children.sort_custom(func(a, b): return a.score > b.score)
    
    # Execute highest scoring child
    if scored_children.size() > 0:
        return scored_children[0].child._tick(delta)
    
    return FAILURE

func _calculate_score(child) -> float:
    # Check if child has custom scoring
    if child.has_method("calculate_utility_score"):
        return child.calculate_utility_score(blackboard)
    
    # Default: use metadata weight
    return child.get_meta("utility_weight", 1.0)
```

**Usage**:
```
BTUtilitySelector
├─── BTSequence (weight=2.0) [Escape]
├─── BTSequence (weight=1.5) [Attack]
└─── BTSequence (weight=0.8) [Collect]
```

### 2. Reactive Interrupt Pattern

For high-priority events that should interrupt current action:

```
Root: BTParallel (policy=REQUIRE_ONE)
│
├─── Danger Monitor (Always Running)
│    └─── BTSequence
│         ├─── BTIsInDanger
│         └─── BTSetInterruptFlag
│
└─── Main Behavior
     └─── BTSelector
          ├─── BTIfInterrupted → Escape
          └─── Normal Behavior
```

### 3. State Machine Hybrid

Combine HSM with BT for complex entity behavior:

```gdscript
# Entity state machine
LimboHSM (root state machine)
├─── IdleState (BTState with idle.tres)
├─── PatrolState (BTState with patrol.tres)
├─── CombatState (BTState with combat.tres)
└─── FleeState (BTState with flee.tres)

# Each state has its own BT
# Transitions are event-based
```

### 4. Coordinated Multi-Agent

For team-based AI coordination:

```
Shared Blackboard (Team level)
├─── team_target (shared target)
├─── team_formation (array of positions)
└─── team_strategy (current strategy)

Bot 1 BT
└─── Uses shared blackboard for coordination

Bot 2 BT
└─── Uses shared blackboard for coordination
```

**Implementation**:
```gdscript
# In game_instance.gd
var team_blackboards: Dictionary = {}  # team_id -> Blackboard

func setup_team(team_id: String):
    team_blackboards[team_id] = Blackboard.new()
    team_blackboards[team_id].set_var("team_target", null)
    team_blackboards[team_id].set_var("members", [])

func add_bot_to_team(bot, team_id: String):
    # Set bot's blackboard parent to team blackboard
    bot.bt_player.blackboard.set_parent(team_blackboards[team_id])
```

---

## Tree Structure Best Practices

### 1. Keep Trees Shallow

❌ **Bad** (too deep):
```
Root
└─── Sequence
     └─── Selector
          └─── Sequence
               └─── Condition
                    └─── Action
```

✅ **Good** (flat):
```
Root: Selector
├─── Sequence (Escape)
│    ├─── Condition
│    └─── Action
└─── Sequence (Attack)
     ├─── Condition
     └─── Action
```

### 2. Use Subtrees for Reusability

```
bot_aggressive.tres
├─── escape_sequence (BTSubtree → escape_common.tres)
├─── attack_sequence (BTSubtree → attack_aggressive.tres)
└─── collect_sequence (BTSubtree → collect_common.tres)

bot_defensive.tres
├─── escape_sequence (BTSubtree → escape_common.tres)
├─── collect_sequence (BTSubtree → collect_common.tres)
└─── hide_sequence (BTSubtree → hide_defensive.tres)
```

### 3. Name Nodes Descriptively

❌ Bad: "BTSequence", "BTSelector", "BTCondition"
✅ Good: "Escape Sequence", "Is In Danger?", "Move To Safety"

Use `_generate_name()` in custom nodes:
```gdscript
func _generate_name() -> String:
    return "Is In Danger? (buffer=%.1fs)" % danger_buffer
```

---

## Debugging Tree Visualization

### Enable Debug Prints

```gdscript
# In custom node
func _tick(delta: float) -> int:
    if OS.is_debug_build():
        print("[%s] Executing for %s" % [get_name(), blackboard.get_var("player")])
    
    # ... logic
    
    if OS.is_debug_build():
        print("[%s] Result: %s" % [get_name(), "SUCCESS" if result == SUCCESS else "FAILURE"])
    
    return result
```

### Visual Debug Overlay

```gdscript
# debug_bt_viewer.gd
extends CanvasLayer

@onready var tree_view = $TreeView

func _process(delta):
    var active_bts = get_tree().get_nodes_in_group("bt_players")
    
    for bt_player in active_bts:
        if bt_player.is_active():
            var active_task = bt_player.get_active_task()
            tree_view.highlight_node(active_task)
```

---

## Performance Considerations

### 1. Tick Rate Optimization

```gdscript
# Vary tick rate based on entity priority
func _physics_process(delta):
    for bot in bots:
        if bot.is_player_nearby:
            # Tick every frame (critical)
            bot.bt_player.update(delta)
        elif Engine.get_physics_frames() % 2 == 0:
            # Tick every other frame (medium priority)
            bot.bt_player.update(delta * 2)
        elif Engine.get_physics_frames() % 4 == 0:
            # Tick every 4 frames (low priority)
            bot.bt_player.update(delta * 4)
```

### 2. Condition Caching

```gdscript
@tool
extends BTCondition

var _cached_result: int = FAILURE
var _cache_time: float = 0.0
@export var cache_duration: float = 0.1  # Cache for 100ms

func _tick(delta: float) -> int:
    var current_time = Time.get_ticks_msec() / 1000.0
    
    # Return cached result if still valid
    if current_time - _cache_time < cache_duration:
        return _cached_result
    
    # Recalculate
    _cached_result = _evaluate()
    _cache_time = current_time
    
    return _cached_result

func _evaluate() -> int:
    # Expensive calculation here
    pass
```

---

## Testing Behavior Trees

### Unit Test Example

```gdscript
# test_bot_escape_behavior.gd
extends GutTest

func test_bot_escapes_from_danger():
    # Setup
    var game_instance = autoqfree(GameInstance.new())
    var bot = autoqfree(ServerPlayer.new())
    game_instance.add_player(-1, "TestBot", Vector2.ZERO, true)
    
    # Place bomb near bot
    var bomb = autoqfree(ServerBomb.new())
    bomb.position = bot.position + Vector2(64, 0)
    game_instance.bombs["test"] = bomb
    
    # Tick BT
    await get_tree().create_timer(0.5).timeout
    
    # Assert bot moved away
    assert_gt(bot.position.distance_to(bomb.position), 64, "Bot should escape from bomb")
```

---

## Conclusion

These examples provide a solid foundation for implementing Behavior Trees in Neptune-Bomberman using LimboAI. Start with simple trees and progressively add complexity as needed.

For implementation details, see `docs/LIMBOAI_REFACTOR_GUIDE.md`.
