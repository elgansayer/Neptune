# LimboAI Refactoring Guide for Neptune-Bomberman

## Executive Summary

This guide provides a comprehensive, step-by-step plan to refactor Neptune-Bomberman's game logic to use **LimboAI** (Behavior Trees) while maintaining the authoritative server architecture.

## Table of Contents

1. [High-Level Strategy & Architecture](#1-high-level-strategy--architecture)
2. [Phased Refactoring Plan](#2-phased-refactoring-plan)
3. [Custom Actions & Conditions](#3-custom-actions--conditions)
4. [Networking & Synchronization](#4-networking--synchronization)
5. [Testing & Debugging](#5-testing--debugging)
6. [Code Examples](#6-code-examples)

---

## 1. High-Level Strategy & Architecture

### 1.1 Where Should Behavior Trees Run?

**Answer: Only on the authoritative server.**

- **Server**: Runs all BTs for both AI bots and player entities
- **Client**: Only sends inputs and renders received state (no BT execution)

**Rationale**: The server is the source of truth. All game logic, including decision-making via BTs, must run server-side to prevent cheating and ensure consistency.

### 1.2 Source of Truth: Server State ↔ Blackboard

The integration follows this flow:

```
Server Game State (game_instance.gd, server_player.gd)
    ↓ (updates)
LimboAI Blackboard (shared data structure)
    ↓ (reads)
Behavior Tree Nodes (conditions, actions)
    ↓ (modifies)
Server Game State
```

**Key Principle**: 
- Game state updates blackboard each frame
- BT tasks read from blackboard
- BT actions modify game state directly (not just blackboard)
- Blackboard acts as a **query interface**, not the primary data store

### 1.3 Tick Strategy

BTs should be ticked in the server's `_physics_process(delta)`:

```gdscript
# In game_instance.gd
func _physics_process(delta):
    # Update blackboards from game state
    _update_blackboards()
    
    # Tick all player BTs
    for peer_id in players:
        var player = players[peer_id]
        if player.bt_player:
            player.bt_player.update(delta)  # LimboAI tick
    
    # Tick bomb BTs (if using BTs for bombs)
    for bomb_id in bombs:
        var bomb = bombs[bomb_id]
        if bomb.bt_player:
            bomb.bt_player.update(delta)
    
    # Existing physics updates...
    # Sync state to clients (unchanged)
    if last_sync_time >= SYNC_INTERVAL:
        sync_state_to_clients()
```

**Why `_physics_process`?**
- Consistent with game physics (60fps)
- Deterministic timing for server authority
- Matches current architecture

### 1.4 Client-Side Cosmetic Trees (Optional)

For advanced visual feedback, clients can run **cosmetic BTs** that:
- Don't affect game state
- Provide visual hints (e.g., AI "thinking" animations)
- Use locally predicted data

**Implementation**: Use separate, simplified BT files marked as "visual only"

---

## 2. Phased Refactoring Plan

### Phase 1: Setup & "Hello World"

#### Step 1.1: Install LimboAI

**For GDExtension Version (Recommended):**

1. Open your project in Godot Editor
2. Go to `AssetLib` tab
3. Search for "LimboAI"
4. Download and install
5. Restart Godot (`Project -> Reload Project`)

**Verification:**
```gdscript
# Test script
extends Node

func _ready():
    var bt = BehaviorTree.new()
    print("LimboAI installed: ", bt != null)
```

#### Step 1.2: Create First BT - Bomb Lifecycle

Create a simple BT for bomb's tick-to-explode cycle:

**File**: `res://shared/ai/limbo_trees/bomb_lifecycle.tres`

**Tree Structure**:
```
Root (BTSequence)
├── BTCheckFuseExpired (Condition)
└── BTExplodeBomb (Action)
```

**Implementation**:

```gdscript
# File: res://shared/ai/limbo_nodes/bt_check_fuse_expired.gd
@tool
extends BTCondition

func _tick(delta: float) -> int:
    var bomb = blackboard.get_var("bomb")
    var current_time = blackboard.get_var("current_time", 0.0)
    
    if bomb.explosion_timer >= GameConfig.BOMB_FUSE_TIME:
        return SUCCESS
    return FAILURE
```

```gdscript
# File: res://shared/ai/limbo_nodes/bt_explode_bomb.gd
@tool
extends BTAction

func _tick(delta: float) -> int:
    var bomb = blackboard.get_var("bomb")
    bomb.explode()  # Call existing explode method
    return SUCCESS
```

**Attach to Bomb**:

```gdscript
# In server_bomb.gd
@onready var bt_player: BTPlayer = $BTPlayer

func _ready():
    bt_player.behavior_tree = preload("res://shared/ai/limbo_trees/bomb_lifecycle.tres")
    bt_player.blackboard.set_var("bomb", self)
```

#### Step 1.3: Verify in Headless Server

Run the server and confirm bombs explode via BT:

```bash
cd server
godot --headless --path . res://server/main_server.tscn
```

---

### Phase 2: Refactoring AI (Bot Logic)

#### Current State: Custom BT System

The project currently uses:
- `BehaviorTreeRunner` (custom implementation)
- `BTUtilitySelector` for behavior scoring
- Custom nodes in `shared/ai/behavior_tree/nodes/`

#### Goal: Migrate to LimboAI

##### Step 2.1: Port AI Conditions

**Example: `IsInDanger` Condition**

**Before** (`shared/ai/behavior_tree/nodes/condition_in_danger.gd`):
```gdscript
extends BTNode

func evaluate(blackboard: Dictionary) -> int:
    var player_tile = blackboard["current_tile"]
    var hazard_predictor = blackboard["hazard_predictor"]
    
    if hazard_predictor.is_tile_dangerous(player_tile):
        return SUCCESS
    return FAILURE
```

**After** (LimboAI version):
```gdscript
# res://shared/ai/limbo_nodes/bt_is_in_danger.gd
@tool
extends BTCondition

@export var danger_buffer: float = 1.0

func _tick(delta: float) -> int:
    var player = blackboard.get_var("player")
    var hazard_predictor = blackboard.get_var("hazard_predictor")
    var player_tile = player.get_tile_position()
    
    if hazard_predictor.is_tile_dangerous(player_tile, danger_buffer):
        return SUCCESS
    return FAILURE
```

##### Step 2.2: Port AI Actions

**Example: `MoveToCell` Action**

**After** (LimboAI version):
```gdscript
# res://shared/ai/limbo_nodes/bt_move_to.gd
@tool
extends BTAction

func _tick(delta: float) -> int:
    var player = blackboard.get_var("player")
    var target_cell = blackboard.get_var("target_cell")
    
    if not target_cell:
        return FAILURE
    
    var target_pos = Vector2(
        target_cell.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2,
        target_cell.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2
    )
    
    # Calculate direction to target
    var direction = (target_pos - player.position).normalized()
    player.set_input(direction.x, direction.y)
    
    # Check if reached (within threshold)
    if player.position.distance_to(target_pos) < GameConfig.TILE_SIZE * 0.3:
        blackboard.set_var("target_cell", null)
        return SUCCESS
    
    return RUNNING
```

##### Step 2.3: Build Bot Behavior Tree

**File**: `res://shared/ai/limbo_trees/bot_balanced.tres`

**Tree Structure**:
```
Root (BTSelector - Priority based)
├── Escape Sequence (High Priority)
│   ├── BTIsInDanger
│   ├── BTFindEscapeRoute
│   └── BTMoveToCell
├── Attack Sequence
│   ├── BTIsOpponentNearby
│   ├── BTFindAttackPosition
│   ├── BTMoveToCell
│   └── BTPlaceBomb
├── Collect Powerup Sequence
│   ├── BTIsPowerupAvailable
│   ├── BTFindNearestPowerup
│   └── BTMoveToCell
└── Idle/Patrol
    └── BTWaitAmbush
```

**Utility Scoring (Custom Decorator)**:

```gdscript
# res://shared/ai/limbo_nodes/bt_utility_decorator.gd
@tool
extends BTDecorator

@export var base_weight: float = 1.0
@export var score_func: Callable

func _tick(delta: float) -> int:
    # Calculate utility score
    var score = base_weight
    if score_func.is_valid():
        score *= score_func.call(blackboard)
    
    blackboard.set_var("last_utility_score", score)
    
    # Always run child (selector will handle priority)
    return get_child(0)._tick(delta)
```

##### Step 2.4: Migrate Bot Controller

**Before** (`ai/bot_controller.gd`):
```gdscript
extends Node
class_name ServerBotController

var _bt_runner  # Custom implementation
var _blackboard := {}

func configure(instance, player, personality_name, ...):
    # ...
    _build_behavior_tree()  # Custom tree building

func _physics_process(delta: float):
    _update_blackboard()
    _bt_runner.tick(delta)
    _apply_outputs()
```

**After** (LimboAI version):
```gdscript
# ai/bot_controller_limbo.gd
extends Node
class_name ServerBotControllerLimbo

var bt_player: BTPlayer
var personality: String

func configure(instance, player, personality_name, sampler, predictor, tracker, planner):
    game_instance = instance
    player_ref = player
    personality = personality_name
    
    # Create BTPlayer
    bt_player = BTPlayer.new()
    add_child(bt_player)
    
    # Load behavior tree based on personality
    var bt_path = "res://shared/ai/limbo_trees/bot_%s.tres" % personality.to_lower()
    bt_player.behavior_tree = load(bt_path)
    
    # Setup blackboard
    _setup_blackboard()
    
    # Connect to player lifecycle
    player_ref.tree_exited.connect(_on_player_removed, CONNECT_ONE_SHOT)

func _setup_blackboard():
    var bb = bt_player.blackboard
    bb.set_var("game_instance", game_instance)
    bb.set_var("player", player_ref)
    bb.set_var("grid_sampler", grid_sampler)
    bb.set_var("hazard_predictor", hazard_predictor)
    bb.set_var("opponent_tracker", opponent_tracker)
    bb.set_var("bomb_planner", bomb_planner)
    bb.set_var("personality", personality)

func _physics_process(delta: float):
    if not is_instance_valid(player_ref) or player_ref.is_dead:
        return
    
    # Update blackboard with fresh data
    _update_blackboard()
    
    # LimboAI automatically ticks when BTPlayer is in scene tree
    # No manual tick needed!

func _update_blackboard():
    var bb = bt_player.blackboard
    bb.set_var("current_tile", player_ref.get_tile_position())
    bb.set_var("time", Time.get_ticks_msec() / 1000.0)
    # Perception systems are updated by bot_manager
```

---

### Phase 3: Refactoring Player Logic (The Core Challenge)

This is the most complex part because **players are controlled by client input, not AI**.

#### Strategy: Input Buffer + BT Consumer

The server buffers client inputs, then a BT "consumes" them to execute actions.

##### Step 3.1: Create Input Buffer System

```gdscript
# res://shared/entities/input_buffer.gd
extends RefCounted
class_name InputBuffer

var inputs: Array[Dictionary] = []
const MAX_BUFFER_SIZE = 10

func push_input(input_data: Dictionary):
    inputs.append(input_data)
    if inputs.size() > MAX_BUFFER_SIZE:
        inputs.pop_front()

func peek_latest() -> Dictionary:
    if inputs.is_empty():
        return {}
    return inputs.back()

func consume_latest() -> Dictionary:
    if inputs.is_empty():
        return {}
    return inputs.pop_back()

func has_input() -> bool:
    return not inputs.is_empty()

func clear():
    inputs.clear()
```

##### Step 3.2: Integrate Input Buffer in ServerPlayer

```gdscript
# In server_player.gd
const InputBufferScript = preload("res://shared/entities/input_buffer.gd")

var input_buffer: InputBuffer = InputBuffer.new()
var bt_player: BTPlayer  # LimboAI player controller

func _ready():
    # Setup collision, shape casts, etc.
    # ...
    
    # Setup player BT
    _setup_player_bt()

func _setup_player_bt():
    bt_player = BTPlayer.new()
    add_child(bt_player)
    
    bt_player.behavior_tree = preload("res://shared/ai/limbo_trees/player_controller.tres")
    
    var bb = bt_player.blackboard
    bb.set_var("player", self)
    bb.set_var("input_buffer", input_buffer)

# Called by game_instance when receiving client RPC
func queue_input(input_data: Dictionary):
    input_buffer.push_input(input_data)
```

##### Step 3.3: Create Player BT

**File**: `res://shared/ai/limbo_trees/player_controller.tres`

**Tree Structure**:
```
Root (BTSequence - Always runs each frame)
├── BTUpdateInputFromBuffer (Action)
└── BTProcessPlayerActions (Selector)
    ├── BTHandlePowerGloveActions (Sequence)
    │   ├── BTHasPowerGlove (Condition)
    │   └── BTProcessPowerGlove (Composite)
    │       ├── BTThrowBomb (if action_pressed && carrying)
    │       ├── BTPickupBomb (if action_pressed && bomb_underfoot)
    │       └── BTPlaceBomb (if action_pressed && can_place)
    └── BTHandleStandardActions (Sequence)
        └── BTPlaceBomb (if place_bomb input)
```

##### Step 3.4: Implement Player BT Nodes

```gdscript
# res://shared/ai/limbo_nodes/bt_update_input_from_buffer.gd
@tool
extends BTAction

## Reads latest input from buffer and stores in blackboard

func _tick(delta: float) -> int:
    var input_buffer = blackboard.get_var("input_buffer")
    var player = blackboard.get_var("player")
    
    if not input_buffer or not player:
        return FAILURE
    
    # Get latest input without consuming (peek)
    var input_data = input_buffer.peek_latest()
    
    if input_data.is_empty():
        # No input, set neutral state
        player.set_input(0.0, 0.0)
        blackboard.set_var("input_x", 0.0)
        blackboard.set_var("input_y", 0.0)
        blackboard.set_var("action_pressed", false)
        blackboard.set_var("place_bomb", false)
        return SUCCESS
    
    # Set movement input (always processed)
    var input_x = input_data.get("input_x", 0.0)
    var input_y = input_data.get("input_y", 0.0)
    player.set_input(input_x, input_y)
    
    # Store in blackboard for action processing
    blackboard.set_var("input_x", input_x)
    blackboard.set_var("input_y", input_y)
    blackboard.set_var("action_pressed", input_data.get("action_pressed", false))
    blackboard.set_var("action_released", input_data.get("action_released", false))
    blackboard.set_var("place_bomb", input_data.get("place_bomb", false))
    
    return SUCCESS
```

```gdscript
# res://shared/ai/limbo_nodes/bt_has_power_glove.gd
@tool
extends BTCondition

func _tick(delta: float) -> int:
    var player = blackboard.get_var("player")
    return SUCCESS if player.has_power_glove else FAILURE
```

```gdscript
# res://shared/ai/limbo_nodes/bt_process_power_glove.gd
@tool
extends BTAction

## Handles Power Glove logic: Throw -> Pickup -> Place

func _tick(delta: float) -> int:
    var player = blackboard.get_var("player")
    var action_pressed = blackboard.get_var("action_pressed", false)
    
    if not action_pressed:
        return SUCCESS  # No action this frame
    
    # Priority 1: Throw if carrying
    if player.is_carrying_bomb():
        player.throw_carried_bomb()
        _consume_input()
        return SUCCESS
    
    # Priority 2: Try pickup
    var game_instance = blackboard.get_var("game_instance")
    if _try_pickup_bomb(player, game_instance):
        _consume_input()
        return SUCCESS
    
    # Priority 3: Place bomb if allowed
    if player.can_place_bomb():
        var player_tile = player.get_tile_position()
        if not _bomb_at_position(player_tile, game_instance):
            game_instance.place_bomb(player)
            _consume_input()
            return SUCCESS
    
    return SUCCESS

func _consume_input():
    var input_buffer = blackboard.get_var("input_buffer")
    input_buffer.consume_latest()

func _try_pickup_bomb(player, game_instance) -> bool:
    # Existing pickup logic from game_instance._try_pickup_bomb_at_player
    var player_tile = player.get_tile_position()
    for bomb_id in game_instance.bombs:
        var bomb = game_instance.bombs[bomb_id]
        if is_instance_valid(bomb) and bomb.get_tile_position() == player_tile:
            if player.try_pickup_bomb(bomb):
                return true
    return false

func _bomb_at_position(tile: Vector2i, game_instance) -> bool:
    for bomb_id in game_instance.bombs:
        var bomb = game_instance.bombs[bomb_id]
        if is_instance_valid(bomb) and bomb.get_tile_position() == tile:
            return true
    return false
```

##### Step 3.5: Before vs After Comparison

**BEFORE** (`server_player.gd` in `_physics_process`):
```gdscript
# OLD: Direct input processing in game_instance.handle_player_input()
func handle_player_input(peer_id: int, input_data: Dictionary):
    if not players.has(peer_id):
        return
    
    var player = players[peer_id]
    player.set_input(input_data.get("input_x", 0.0), input_data.get("input_y", 0.0))
    
    var action_pressed = input_data.get("action_pressed", false)
    
    if player.has_power_glove:
        if action_pressed:
            if player.is_carrying_bomb():
                player.throw_carried_bomb()
            else:
                var pickup_successful = _try_pickup_bomb_at_player(player)
                if not pickup_successful:
                    # Place bomb logic
                    if player.can_place_bomb():
                        place_bomb(player)
    else:
        if input_data.get("place_bomb", false) and player.can_place_bomb():
            place_bomb(player)
```

**AFTER** (BT-based):
```gdscript
# NEW: In game_instance.handle_player_input()
func handle_player_input(peer_id: int, input_data: Dictionary):
    if not players.has(peer_id):
        return
    
    var player = players[peer_id]
    # Simply queue the input; BT will process it
    player.queue_input(input_data)

# In _physics_process()
func _physics_process(delta):
    # BTs are automatically ticked (they're in scene tree)
    # No manual processing needed - LimboAI handles it!
    
    # Rest of physics logic...
```

**Key Benefit**: All player logic is now in the BT, making it:
- Easier to visualize
- Easier to debug (LimboAI debugger)
- Easier to modify without touching core code
- Consistent with AI bot logic

---

### Phase 4: State Management & Blackboard

#### Blackboard Best Practices

##### Global vs Local Blackboard

**Local Blackboard** (per-entity):
```gdscript
# Each player/bot has their own
var bb = bt_player.blackboard
bb.set_var("player", self)
bb.set_var("current_tile", get_tile_position())
bb.set_var("carried_bomb", carried_bomb)
```

**Shared Blackboard** (game-wide):
```gdscript
# In game_instance.gd
var shared_blackboard: Blackboard = Blackboard.new()

func _ready():
    shared_blackboard.set_var("game_instance", self)
    shared_blackboard.set_var("ai_manager", ai_manager)
    shared_blackboard.set_var("threat_matrix", ai_manager.threat_matrix)

# Each entity references the shared blackboard
func add_player(...):
    # ...
    player.bt_player.blackboard.set_parent(shared_blackboard)
```

**What Goes in Blackboard?**

✅ **DO Store**:
- Entity references (player, bomb, game_instance)
- Perception systems (hazard_predictor, opponent_tracker)
- Current state snapshots (current_tile, health, powerups)
- Temporary decisions (target_cell, escape_route)

❌ **DON'T Store**:
- Large data structures (entire game map)
- Data that's already in entities (use references instead)
- Network sync data (blackboard is server-only)

##### Blackboard Update Pattern

```gdscript
# In game_instance.gd
func _physics_process(delta):
    # 1. Update shared blackboard
    shared_blackboard.set_var("current_time", Time.get_ticks_msec() / 1000.0)
    shared_blackboard.set_var("threat_matrix", ai_manager.threat_matrix)
    
    # 2. Update per-player blackboards
    for peer_id in players:
        var player = players[peer_id]
        if player.bt_player:
            var bb = player.bt_player.blackboard
            bb.set_var("current_tile", player.get_tile_position())
            bb.set_var("health", player.health if player.has("health") else 100)
            bb.set_var("powerups", {
                "max_bombs": player.max_bombs,
                "bomb_range": player.bomb_range,
                "has_kicker": player.has_bomb_kicker,
                "has_glove": player.has_power_glove
            })
    
    # 3. LimboAI ticks BTs automatically (no manual tick needed)
    
    # 4. Rest of physics...
```

---

### Phase 5: Integration & Testing

#### Testing Checklist

- [ ] Bot movement matches original behavior
- [ ] Bot bomb placement is tactical (not suicidal)
- [ ] Bot power-up collection works
- [ ] Bot escapes danger appropriately
- [ ] Player movement feels responsive
- [ ] Player bomb placement works with Power Glove
- [ ] Player bomb throwing works
- [ ] Multiplayer: Multiple players can play simultaneously
- [ ] Multiplayer: Bot vs Human interactions work
- [ ] Network: State sync is unchanged (no new desyncs)
- [ ] Performance: No noticeable FPS drop

#### Common Issues & Solutions

**Issue**: Player input feels laggy
- **Cause**: Input buffer is too large or BT tick is slow
- **Solution**: Reduce buffer size, optimize BT conditions

**Issue**: Bots commit suicide frequently
- **Cause**: Danger detection not working in BT
- **Solution**: Verify `hazard_predictor` is passed to blackboard correctly

**Issue**: BT debugger shows nothing
- **Cause**: Running in headless server mode
- **Solution**: Use debug prints or run server with display for debugging

---

## 3. Custom Actions & Conditions

### Essential Custom Nodes

#### Conditions

```gdscript
# 1. IsCellWalkable
@tool
extends BTCondition
@export var cell_var: StringName = &"target_cell"

func _tick(delta: float) -> int:
    var grid_sampler = blackboard.get_var("grid_sampler")
    var cell = blackboard.get_var(cell_var)
    return SUCCESS if grid_sampler.is_tile_walkable(cell) else FAILURE
```

```gdscript
# 2. HasPowerup
@tool
extends BTCondition
@export var powerup_type: String = "bomb_kicker"

func _tick(delta: float) -> int:
    var player = blackboard.get_var("player")
    match powerup_type:
        "bomb_kicker": return SUCCESS if player.has_bomb_kicker else FAILURE
        "power_glove": return SUCCESS if player.has_power_glove else FAILURE
        _: return FAILURE
```

```gdscript
# 3. HasClientInput
@tool
extends BTCondition
@export var input_action: String = "action_pressed"

func _tick(delta: float) -> int:
    var input_val = blackboard.get_var(input_action, false)
    return SUCCESS if input_val else FAILURE
```

#### Actions

```gdscript
# 1. MoveToCell
@tool
extends BTAction

func _tick(delta: float) -> int:
    var player = blackboard.get_var("player")
    var target_cell = blackboard.get_var("target_cell")
    
    if not target_cell:
        return FAILURE
    
    var target_pos = Vector2(
        target_cell.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2,
        target_cell.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2
    )
    
    var direction = (target_pos - player.position).normalized()
    player.set_input(direction.x, direction.y)
    
    if player.position.distance_to(target_pos) < GameConfig.TILE_SIZE * 0.3:
        blackboard.set_var("target_cell", null)
        return SUCCESS
    
    return RUNNING
```

```gdscript
# 2. PlantBomb
@tool
extends BTAction

func _tick(delta: float) -> int:
    var player = blackboard.get_var("player")
    var game_instance = blackboard.get_var("game_instance")
    
    if not player.can_place_bomb():
        return FAILURE
    
    game_instance.place_bomb(player)
    return SUCCESS
```

```gdscript
# 3. ConsumeClientInput
@tool
extends BTAction

func _tick(delta: float) -> int:
    var input_buffer = blackboard.get_var("input_buffer")
    input_buffer.consume_latest()
    return SUCCESS
```

---

## 4. Networking & Synchronization

### Does This Affect Network Traffic?

**Answer: No, network traffic is unchanged.**

**Why?**
1. BTs run **only on server**
2. BTs modify **server game state** (player positions, bomb placements)
3. Existing `sync_state_to_clients()` continues to work unchanged
4. Clients receive the **same state updates** as before

### Diagram

```
[Client] --> RPC input --> [Server]
                              ↓
                        [Input Buffer]
                              ↓
                        [BT Processes Input]
                              ↓
                        [Modifies Game State]
                              ↓
                        [Sync State to Clients] (unchanged)
                              ↓
[Client] <-- State Update <---
```

### New Desynchronization Risks

**Risk 1: Non-Deterministic BT Execution**
- **Cause**: Random actions in BT
- **Prevention**: Use seeded RNG in blackboard

**Risk 2: Blackboard State Inconsistency**
- **Cause**: Blackboard not updated before BT tick
- **Prevention**: Always update blackboard in `_physics_process` before BTs tick

**Risk 3: Input Buffer Race Condition**
- **Cause**: Input arrives mid-frame
- **Prevention**: Use Godot's RPC queue (already handled by engine)

---

## 5. Testing & Debugging

### Debugging Networked BTs

#### Option 1: LimboAI Visual Debugger (Editor Only)

1. Run server **with display** (not headless):
```bash
godot --path ./server res://server/main_server.tscn
```

2. In Godot Editor:
   - Bottom panel → LimboAI Debugger
   - Select running instance
   - View active BT nodes

#### Option 2: Debug Prints

```gdscript
# In custom BT node
func _tick(delta: float) -> int:
    print("[BT] %s - Input: %s" % [name, blackboard.get_var("input_x")])
    # ... logic
    print("[BT] %s - Result: %s" % [name, "SUCCESS" if result == SUCCESS else "RUNNING"])
    return result
```

#### Option 3: Custom Debug UI

```gdscript
# res://server/debug_bt_overlay.gd
extends CanvasLayer

@onready var label = $Label

func _process(delta):
    if not get_tree().get_first_node_in_group("players"):
        return
    
    var player = get_tree().get_first_node_in_group("players")
    if player.bt_player:
        var active_task = player.bt_player.get_active_task()
        label.text = "Active Task: %s" % (active_task.name if active_task else "None")
```

#### Option 4: Unit Tests

```gdscript
# res://tests/test_player_bt.gd
extends GutTest

func test_player_places_bomb_on_input():
    var game_instance = GameInstance.new()
    add_child_autofree(game_instance)
    
    var player = ServerPlayer.new()
    game_instance.add_player(1, "TestPlayer")
    
    # Simulate input
    player.queue_input({"place_bomb": true})
    
    # Tick BT
    await get_tree().process_frame
    
    # Assert
    assert_eq(game_instance.bombs.size(), 1, "Bomb should be placed")
```

### Performance Monitoring

```gdscript
# In game_instance.gd
var bt_tick_time := 0.0

func _physics_process(delta):
    var start = Time.get_ticks_usec()
    
    # BT ticking happens automatically
    
    bt_tick_time = (Time.get_ticks_usec() - start) / 1000.0  # Convert to ms
    
    # Print every second
    if Engine.get_physics_frames() % 60 == 0:
        print("[Performance] BT tick time: %.2f ms" % bt_tick_time)
```

---

## 6. Code Examples

### Complete Bot BT Example

```gdscript
# res://shared/ai/limbo_trees/bot_aggressive.tres
# (Created in Godot Editor)

# Tree structure:
# BTSelector (root)
# ├── BTSequence [weight=2.0] (Escape)
# │   ├── BTIsInDanger
# │   ├── BTFindEscapeRoute
# │   └── BTMoveToCell
# ├── BTSequence [weight=1.5] (Attack)
# │   ├── BTIsOpponentNearby [max_distance=5]
# │   ├── BTFindAttackPosition
# │   ├── BTMoveToCell
# │   └── BTPlaceBomb
# └── BTWander (fallback)
```

### Complete Player BT Example

```gdscript
# res://shared/ai/limbo_trees/player_controller.tres

# Tree structure:
# BTSequence (root)
# ├── BTUpdateInputFromBuffer
# └── BTSelector (Actions)
#     ├── BTSequence (Power Glove)
#     │   ├── BTHasPowerGlove
#     │   └── BTProcessPowerGlove
#     └── BTSequence (Standard)
#         ├── BTCheckPlaceBombInput
#         └── BTPlaceBomb
```

---

## Conclusion

This refactoring transforms Neptune-Bomberman's logic into a modular, visual, and debuggable system using LimboAI while preserving the authoritative server architecture. The phased approach ensures minimal disruption and allows incremental testing.

### Next Steps

1. Install LimboAI GDExtension
2. Start with Phase 1 (Bomb lifecycle)
3. Progress through phases, testing at each step
4. Use LimboAI debugger extensively
5. Enjoy cleaner, more maintainable AI code!

### Resources

- [LimboAI Documentation](https://limboai.readthedocs.io/)
- [LimboAI GitHub](https://github.com/limbonaut/limboai)
- [Behavior Trees Introduction](https://limboai.readthedocs.io/en/stable/behavior-trees/introduction.html)
- [Creating Custom Tasks](https://limboai.readthedocs.io/en/stable/behavior-trees/custom-tasks.html)
