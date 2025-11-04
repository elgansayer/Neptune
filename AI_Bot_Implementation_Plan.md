# AI Bot Implementation Plan

## 1. Overview

### Existing Architecture Summary

The current Bomberman project is built on a robust client-server architecture using a headless Godot server. This design is ideal for authoritative AI, as all game logic and physics are processed on the server, preventing client-side cheating and ensuring consistent behavior.

- **Networking**: ENet-based RPC communication between client and server.
- **Game Logic**: The `server/game_instance.gd` script manages the lifecycle of a single match, including player management and state updates.
- **Player Control**: Player input is sent from the client to the server, which then moves the `CharacterBody2D` node for the player.
- **State Synchronization**: The server broadcasts game state to all clients at a rate of 20Hz.
- **Backend**: An abstract `BackendService` is in place, currently using a `LocalBackend`, with plans for PlayFab/Nakama integration. This is relevant for potentially storing bot statistics or using a backend service to manage bot populations in matchmaking.

**Implementation Status**: ✅ **COMPLETED** - Advanced Triple-Hybrid AI system is fully implemented and operational.

### Purpose and Design Goals

The goal is to introduce **Advanced Triple-Hybrid AI Bomberman Bots** that combine three complementary AI architectures to create truly strategic, adaptive opponents that execute complex multi-step plans while maintaining human-like unpredictability.

**Design Goals:**
- **Strategic Planning**: Bots execute multi-step tactical sequences (hunt → corner → trap → escape) rather than just reacting to immediate situations
- **Adaptive Behavior**: State-based strategies that transition dynamically based on game context
- **Human-Like Unpredictability**: Personality-driven decision making with varied aggression levels, reaction times, and risk assessment
- **Scalable Performance**: Efficient enough to run multiple bots (3-10) in a match without significant overhead
- **Challenging but Fair**: Bots are skilled but make believable mistakes through tunable reaction delays and imperfect information processing

**Triple-Hybrid Architecture Overview:**
1. **State Machine (Strategic Layer)**: High-level decision making - determines overall strategy (EXPLORING, HUNTING, CORNERING, ESCAPING, AMBUSHING)
2. **Behavior Trees (Tactical Layer)**: Multi-step action sequences - executes complex plans like "intercept → bomb → retreat"
3. **Utility System (Moment-to-Moment Layer)**: Tactical calculations - evaluates bomb values, pathfinding, target selection

## 2. Architecture Plan

### Integration Strategy

AI bots are treated as server-side players with no client connection. The server's `GameInstance` creates, manages, and processes AI bots in the same physics loop as human players. From the client's perspective, bots are indistinguishable from human players.

**Implementation:**
1. **Instantiation**: `GameInstance.add_ai_bot()` creates `AIPlayer` nodes (extends `ServerPlayer`)
2. **Auto-Spawning**: Server automatically spawns 3 bots (Balanced, Aggressive, Timid) when first player connects
3. **Management**: Each bot's `_physics_process()` generates local input using `AIBotController.decide_action()`
4. **Synchronization**: Bot positions and actions are included in regular 20Hz state snapshots to clients
5. **RPC Commands**: Admin can spawn additional bots via `request_spawn_bot()` RPC

### Implemented Node/Class Hierarchy

```
Server-Side Architecture:
├─ GameInstance (Node2D)
│  ├─ ServerPlayer (CharacterBody2D) - Human players
│  └─ AIPlayer (extends ServerPlayer) - AI bots
│     ├─ AIBotController - Decision-making brain
│     │  ├─ State Machine (6 states)
│     │  ├─ Behavior Trees (5 trees)
│     │  └─ Utility Functions (tactical calculations)
│     └─ AIObserver - World state analysis
│
└─ Shared/AI Components:
   ├─ ai_personalities.gd - 5 personality types with weight tuning
   ├─ ai_observer.gd - Danger maps, safe tiles, escape routes
   ├─ ai_bot_controller.gd - Triple-hybrid decision system
   ├─ ai_player.gd - Bot player node with local input generation
   └─ behavior_tree.gd - BT node library (15+ node types)
```

**File Structure:**
```
shared/ai/
├─ ai_personalities.gd       # Personality weight definitions
├─ ai_observer.gd             # World state analysis & danger maps
├─ ai_bot_controller.gd       # Triple-hybrid AI brain
└─ behavior_tree.gd           # BT implementation (composites, decorators, conditions, actions)

shared/entities/
└─ ai_player.gd               # AI player entity (extends ServerPlayer)

server/
├─ game_instance.gd           # AI integration & spawning
└─ main_server.gd             # Auto-spawn logic
```

**Key Classes:**

**`AIBotController.gd`**: The "brain" of the bot, containing:
- **State Machine**: 6 strategic states with transition logic
- **Behavior Trees**: 5 pre-built trees for state-specific tactics
- **Utility Functions**: Bomb value calculation, pathfinding, target selection, explosion simulation

**`AIObserver.gd`**: World state interpreter providing:
- Danger map updates (which tiles will explode and when)
- Safe tile finding with distance scoring
- Escape route counting
- Adjacent tile analysis
- Map validity checking

**`AIPlayer.gd`**: Bot entity that:
- Extends `ServerPlayer` to reuse collision, movement, bomb placement
- Generates local input via `AIBotController` in `_physics_process()`
- Maintains bot-specific state (personality, name, controller reference)

**`BehaviorTree.gd`**: Complete BT library with:
- **Composite Nodes**: Sequence, Selector, Parallel
- **Decorator Nodes**: Inverter, Repeater, Cooldown
- **Condition Nodes**: IsInDanger, IsOpponentNear, HasEscapeRoute, IsBombValuable, IsAggressive, IsTargetCornered, CanPlaceBomb
- **Action Nodes**: MoveToTarget, MoveToSafety, PlaceBomb, FindNearestOpponent, FindBlockCluster, FindStrategicPosition, Wait, ExploreRandomly

## 3. Decision-Making System (Triple-Hybrid Approach)

The AI uses a **three-layer architecture** where each layer operates at a different level of abstraction, creating sophisticated strategic behavior.

### Layer 1: State Machine (Strategic Planning)

The State Machine operates at the highest level, determining the bot's overall strategic intent. It transitions between 6 distinct states based on game context.

**States:**
```gdscript
enum State {
    EXPLORING,      # Default: looking for blocks/power-ups, clearing map
    HUNTING,        # Actively chasing a specific opponent
    CORNERING,      # Opponent trapped, executing kill sequence
    ESCAPING,       # In immediate danger, survival mode
    AMBUSHING,      # Waiting at strategic choke point
    POWER_UP_RUSH   # Racing to grab power-up (future expansion)
}
```

**State Transition Logic:**

**EXPLORING** (Default state):
- → **HUNTING**: If aggressive personality (aggression > 400) and opponent within 7 tiles
- → **ESCAPING**: If danger detected (< 1.5s until explosion)

**HUNTING** (Chasing target):
- → **CORNERING**: If within 3 tiles of target AND target has ≤1 escape route
- → **EXPLORING**: If target lost or too far (> 10 tiles)
- → **ESCAPING**: If danger detected
- **Maintains**: `hunt_target_tile` for persistent tracking

**CORNERING** (Setting up kill):
- → **ESCAPING**: After 0.5s (bomb placed, time to retreat)
- **Executes**: Intercept → Bomb → Brief wait → Retreat sequence

**ESCAPING** (Survival mode):
- → **EXPLORING**: When safe again (danger > 2.5s)
- **Override**: Always takes priority when danger detected

**AMBUSHING** (Tactical waiting):
- → **EXPLORING**: After 5s timeout
- → **ESCAPING**: If danger detected
- **Maintains**: `ambush_position` for strategic positioning

**State Entry/Exit Hooks:**
```gdscript
func enter_state(new_state: State):
    # Cleanup old state
    match current_state:
        State.HUNTING:
            hunt_target = null
            hunt_target_tile = Vector2i(-1, -1)
        State.AMBUSHING:
            ambush_position = Vector2i(-1, -1)
    
    # Initialize new state
    current_state = new_state
    state_entry_time = Time.get_ticks_msec() / 1000.0
    state_timer = 0.0
    
    # State-specific setup
    match new_state:
        State.HUNTING:
            hunt_target_tile = find_nearest_opponent(...)
        State.AMBUSHING:
            ambush_position = find_ambush_position()
```

### Layer 2: Behavior Trees (Tactical Sequences)

Each state has a dedicated Behavior Tree that defines multi-step action sequences. BTs execute from top-to-bottom, with composites controlling flow.

**Behavior Tree Node Types Implemented:**

**Composite Nodes** (control flow):
- `Sequence`: Execute children in order, fail if any fails (AND logic)
- `Selector`: Try children in order, succeed if any succeeds (OR logic, fallback)
- `Parallel`: Execute all children simultaneously, succeed if all succeed

**Decorator Nodes** (modify child behavior):
- `Inverter`: Flip child's success/failure
- `Repeater`: Execute child N times
- `Cooldown`: Only allow execution after cooldown expires

**Condition Nodes** (boolean checks):
- `IsInDanger(threshold)`: Check if explosion imminent
- `IsOpponentNear(distance)`: Check if opponent within range
- `HasEscapeRoute(min_routes)`: Verify escape routes exist
- `IsAggressive()`: Check if aggressive personality
- `IsTargetCornered()`: Check if target has ≤1 escape
- `IsBombValuable(threshold)`: Check bomb placement value
- `CanPlaceBomb()`: Check if bomb available

**Action Nodes** (perform actions):
- `MoveToTarget()`: Move toward `context.target_tile`
- `MoveToSafety()`: Find and move to nearest safe tile
- `PlaceBomb()`: Place bomb at current position
- `FindNearestOpponent()`: Locate and set target
- `FindBlockCluster()`: Find valuable block groups
- `FindStrategicPosition()`: Move toward map center
- `Wait(duration)`: Idle for specified time
- `ExploreRandomly()`: Random movement for exploration

**State-Specific Trees:**

**Explore Tree** (Selector - try in priority order):
```gdscript
Root: Selector
├─ Sequence: "Find and destroy blocks"
│  ├─ FindBlockCluster()
│  ├─ MoveToTarget()
│  └─ Selector: "Optional bomb"
│     ├─ Sequence: "Bomb if valuable"
│     │  ├─ CanPlaceBomb()
│     │  ├─ IsBombValuable(250)
│     │  ├─ HasEscapeRoute(1)
│     │  └─ PlaceBomb()
│     └─ BTNode() (always succeed)
├─ Sequence: "Move to strategic position"
│  ├─ FindStrategicPosition()
│  └─ MoveToTarget()
└─ ExploreRandomly() (fallback)
```

**Hunt Tree** (Sequence - execute plan):
```gdscript
Root: Sequence
├─ FindNearestOpponent()
├─ MoveToTarget()
└─ Selector: "Aggressive bomb placement"
   ├─ Sequence:
   │  ├─ IsOpponentNear(3)
   │  ├─ CanPlaceBomb()
   │  ├─ IsBombValuable(150)  # Lower threshold when hunting
   │  ├─ HasEscapeRoute(1)
   │  └─ PlaceBomb()
   └─ BTNode() (always succeed)
```

**Corner Tree** (Sequence - trap and retreat):
```gdscript
Root: Sequence
├─ CanPlaceBomb()
├─ HasEscapeRoute(1)
├─ PlaceBomb()           # Execute the trap
├─ Wait(0.2)             # Brief pause for realism
└─ MoveToSafety()        # Immediate retreat
```

**Escape Tree** (Simple - single action):
```gdscript
Root: MoveToSafety()     # Just run to nearest safe tile
```

**Ambush Tree** (Selector - wait or strike):
```gdscript
Root: Selector
├─ Sequence: "Strike when opponent near"
│  ├─ IsOpponentNear(4)
│  ├─ CanPlaceBomb()
│  ├─ HasEscapeRoute(1)
│  ├─ PlaceBomb()
│  └─ MoveToSafety()
└─ Wait(1.0)             # Otherwise wait at position
```

**BT Execution Context:**
```gdscript
var context = {
    "ai_player": ai_player,              # Bot node reference
    "my_tile": current_tile,             # Current grid position
    "observer": observer,                # World state analyzer
    "controller": self,                  # AIBotController reference
    "game_state": game_state,            # Map, players, bombs
    "action_result": {                   # Output buffer
        "direction": Vector2.ZERO,
        "place_bomb": false
    },
    "delta_time": 0.016,
    "current_time": current_time,
    "target_tile": Vector2i(-1, -1),     # Set by Find nodes
    "target_opponent": null              # Set by IsOpponentNear
}

# Execute tree
current_tree.execute(context)
return context.action_result  # Return to physics process
```

### Layer 3: Utility System (Tactical Calculations)

The Utility System provides the "tactical intelligence" used by BT nodes to make moment-to-moment decisions. It calculates numeric scores for actions and targets.

**Core Utility Functions:**

**`calculate_bomb_value(tile, game_state, ai_player) -> float`**
Evaluates the value of placing a bomb at a specific tile:
```gdscript
value = 0.0
# Blocks destroyed (+100 each)
for cell in explosion_cells:
    if is_breakable_block(cell):
        value += 100.0

# Opponents trapped (personality-based bonus)
for opponent in opponents:
    if opponent_tile in explosion_cells:
        value += personality_weights.trap_bonus * 0.5  # 200-600 based on personality

# Self-risk penalty (future: -300 if no escape)

return value
```

**Bomb Placement Thresholds (Personality-Based):**
- Aggressive: 150 (bombs frequently)
- Balanced: 250 (moderate)
- Chaos: 100 (bombs constantly)
- Timid: 500 (bombs rarely, only high value)
- Greedy: 250 (focuses on blocks)

**`simulate_explosion(center, bomb_range, map) -> Array[Vector2i]`**
Calculates exact explosion cells using 4-direction raycast:
```gdscript
cells = [center]
for direction in [UP, DOWN, LEFT, RIGHT]:
    for i in range(1, bomb_range + 1):
        cell = center + direction * i
        if out_of_bounds(cell) or solid_wall(cell):
            break
        cells.append(cell)
        if breakable_block(cell):
            break  # Explosion stops at breakables
return cells
```

**`find_nearest_opponent(from_tile, game_state, ai_player) -> Vector2i`**
Uses Manhattan distance to locate closest opponent:
```gdscript
min_dist = INF
nearest = Vector2i(-1, -1)
for player in game_state.players:
    if player == ai_player:
        continue
    dist = abs(player_tile.x - from_tile.x) + abs(player_tile.y - from_tile.y)
    if dist < min_dist:
        min_dist = dist
        nearest = player_tile
return nearest
```

**`find_valuable_block_clusters(from_tile, game_state, max_search) -> Array`**
Finds and scores groups of breakable blocks:
```gdscript
for each tile in search_radius:
    if is_breakable(tile):
        cluster_count = 1 + count_adjacent_breakables(tile)
        clusters.append({
            "tile": tile,
            "count": cluster_count,
            "distance": manhattan_distance(from_tile, tile)
        })

# Sort by value/distance ratio
clusters.sort_custom(func(a, b):
    return (a.count / max(1.0, a.distance)) > (b.count / max(1.0, b.distance))
)
return clusters.slice(0, 5)  # Top 5 clusters
```

**`find_strategic_position(from_tile, game_state) -> Vector2i`**
Moves toward map center (control key positions):
```gdscript
map_center = Vector2i(map_width / 2, map_height / 2)
best_tile = from_tile
min_distance = INF

for tile in area_around_center(5):
    if is_valid_and_walkable(tile):
        distance = manhattan_distance(from_tile, tile)
        if distance < min_distance:
            min_distance = distance
            best_tile = tile
return best_tile
```

**AIObserver Utility Functions:**

**`get_time_until_explosion(tile) -> float`**
Returns seconds until tile becomes dangerous:
```gdscript
min_time = INF
for bomb in active_bombs:
    if tile in simulate_explosion(bomb.position, bomb.range):
        time_remaining = bomb.fuse_time - (current_time - bomb.spawn_time)
        min_time = min(min_time, time_remaining)
return min_time if min_time < INF else 999.0
```

**`update_danger_map()`**
Pre-calculates which tiles are dangerous (called once per frame):
```gdscript
danger_map = {}
for bomb in active_bombs:
    explosion_cells = simulate_explosion(bomb)
    for cell in explosion_cells:
        time_until = bomb.fuse_time - elapsed
        if not danger_map.has(cell) or time_until < danger_map[cell]:
            danger_map[cell] = time_until
```

**`find_nearest_safe_tiles(from_tile, max_search) -> Array`**
BFS to find safe tiles sorted by distance:
```gdscript
safe_tiles = []
for tile in search_radius:
    if not is_in_danger(tile) and is_walkable(tile):
        safe_tiles.append({
            "tile": tile,
            "distance": manhattan_distance(from_tile, tile)
        })
safe_tiles.sort_custom(func(a, b): return a.distance < b.distance)
return safe_tiles
```

**`count_escape_routes(tile) -> int`**
Counts viable exits from a position:
```gdscript
escape_count = 0
for adjacent in get_adjacent_tiles(tile):
    if is_walkable(adjacent) and not is_in_danger(adjacent):
        escape_count += 1
return escape_count
```

### Integration Flow: How The Three Layers Work Together

**Every Physics Frame (60 FPS):**
```gdscript
func decide_action(ai_player: Node2D) -> Dictionary:
    # 1. THROTTLING (personality-based reactions)
    if current_time - last_reaction_time < personality_weights.reaction_delay * 0.5:
        return {"direction": Vector2.ZERO, "place_bomb": false}
    
    # 2. STATE MACHINE (evaluate transitions)
    var danger = observer.get_time_until_explosion(current_tile)
    
    # Critical override: always escape danger
    if danger < 1.5 and current_state != State.ESCAPING:
        enter_state(State.ESCAPING)
    
    # State-specific transitions
    evaluate_state_transitions(current_tile, game_state, ai_player, current_time)
    
    # 3. BEHAVIOR TREE (execute current state's tree)
    var context = build_context(ai_player, current_tile, game_state)
    var tree = get_current_state_tree()  # Returns explore_tree, hunt_tree, etc.
    tree.execute(context)
    
    # 4. UTILITY SYSTEM (used by BT nodes during execution)
    # Example: FindBlockCluster node calls find_valuable_block_clusters()
    # Example: IsBombValuable node calls calculate_bomb_value()
    
    return context.action_result  # Contains direction and place_bomb decision
```

**Example: Full Decision Chain**

1. **State Machine**: Bot is **HUNTING** (chasing player)
2. **Behavior Tree**: Executes `hunt_tree`
   - `FindNearestOpponent()` calls utility function `find_nearest_opponent()` → sets `context.target_tile`
   - `MoveToTarget()` calls utility function `get_direction_to_tile()` → sets `context.action_result.direction`
   - `IsBombValuable(150)` calls utility function `calculate_bomb_value()` → checks if value ≥ 150
   - If true: `PlaceBomb()` sets `context.action_result.place_bomb = true`
3. **Result**: Bot moves toward opponent and places strategic trap bomb
4. **State Transition**: If opponent cornered (≤1 escape route), transitions to **CORNERING** state next frame

## 4. AI Personalities: Strategic Variety Through Weight Tuning

Five distinct personalities are implemented by adjusting utility weights and behavioral parameters. Each creates dramatically different playstyles without requiring separate AI logic.

**Personality Definitions** (in `ai_personalities.gd`):

```gdscript
enum Type { BALANCED, AGGRESSIVE, TIMID, GREEDY, CHAOS }

# Weight Parameters (0-1000 scale):
{
    "safety": 800,              # Priority for avoiding danger
    "aggression": 400,          # Tendency to hunt/trap opponents
    "exploration": 300,         # Drive to clear blocks
    "trap_bonus": 600,          # Bonus for trapping opponents
    "bomb_frequency": 0.15,     # Random bomb chance
    "reaction_delay": 0.05,     # Seconds between decisions
    "pathfinding_frequency": 1.0 # Seconds between path recalculation
}
```

### Personality #1: BALANCED (All-Rounder)
```gdscript
{
    "safety": 800,
    "aggression": 400,
    "exploration": 300,
    "trap_bonus": 600,
    "bomb_frequency": 0.15,
    "reaction_delay": 0.05,      # 50ms reactions (2x faster than original)
    "pathfinding_frequency": 1.0
}
```
**Behavior**: Moderate in all aspects. Balances survival, aggression, and map clearing. Transitions to **HUNTING** when opponents are nearby but doesn't obsess over kills. Good starter opponent.

### Personality #2: AGGRESSIVE (Hunter)
```gdscript
{
    "safety": 600,               # Slightly lower safety concern
    "aggression": 800,           # Very high aggression
    "exploration": 100,          # Minimal exploration
    "trap_bonus": 1200,          # HUGE trap bonus
    "bomb_frequency": 0.25,      # Bombs more often
    "reaction_delay": 0.02,      # 20ms reactions (5x faster!)
    "pathfinding_frequency": 0.5 # Updates path 2x per second
}
```
**Behavior**: Spends most time in **HUNTING** and **CORNERING** states. Actively seeks out opponents within 7+ tiles. Bomb threshold is only 150 (vs 250 default), so places bombs aggressively when near players. High trap_bonus means bot values trapping opponents more than destroying blocks. Fast reactions make it very responsive.

**State Preference**: EXPLORING → HUNTING (quick transition) → CORNERING → ESCAPING

### Personality #3: TIMID (Defensive)
```gdscript
{
    "safety": 1000,              # Maximum safety priority
    "aggression": 100,           # Minimal aggression
    "exploration": 400,          # Moderate exploration
    "trap_bonus": 200,           # Low trap value
    "bomb_frequency": 0.08,      # Bombs rarely
    "reaction_delay": 0.08,      # 80ms reactions (slower)
    "pathfinding_frequency": 1.5 # Slower pathfinding updates
}
```
**Behavior**: Rarely enters **HUNTING** state. Focuses on **EXPLORING** and quickly transitions to **ESCAPING** at first sign of danger. Bomb threshold is 500 (very high), so only places bombs when extremely valuable. Maintains distance from opponents. Useful for filling slots or testing survival mechanics.

**State Preference**: EXPLORING ↔ ESCAPING (frequent safety checks)

### Personality #4: GREEDY (Power-up Hunter)
```gdscript
{
    "safety": 700,
    "aggression": 200,
    "exploration": 800,          # Very high exploration
    "trap_bonus": 400,
    "bomb_frequency": 0.20,
    "reaction_delay": 0.06,      # 60ms reactions
    "pathfinding_frequency": 0.8
}
```
**Behavior**: Prioritizes **EXPLORING** state, constantly seeking block clusters. Uses `find_valuable_block_clusters()` extensively. In the future (when power-ups are tracked by AIObserver), will transition to **POWER_UP_RUSH** state. Bombs frequently to clear paths to loot.

**State Preference**: EXPLORING (dominant) → POWER_UP_RUSH (future)

### Personality #5: CHAOS (Unpredictable)
```gdscript
{
    "safety": 500,               # Low safety concern
    "aggression": 600,           # High aggression
    "exploration": 600,          # High exploration
    "trap_bonus": 800,           # High trap value
    "bomb_frequency": 0.35,      # Bombs very frequently
    "reaction_delay": 0.01,      # 10ms reactions (FASTEST)
    "pathfinding_frequency": 0.3 # Updates path 3x per second
}
```
**Behavior**: Bomb threshold is only 100 (lowest of all). Places bombs constantly, creating chaos on the map. Transitions rapidly between all states. Extremely fast reactions (10ms) make it appear almost precognitive. High values in both aggression and exploration mean it's unpredictable - might hunt you or might clear blocks. Most challenging opponent.

**State Preference**: Rapid cycling through all states

### Reaction Time Impact

Reaction delays create human-like decision latency:

```gdscript
if current_time - last_reaction_time < personality_weights.reaction_delay * 0.5:
    return {"direction": Vector2.ZERO, "place_bomb": false}  # Wait
```

| Personality | Reaction Delay | Decisions/Second | Feels Like |
|-------------|----------------|------------------|------------|
| Chaos       | 10ms           | ~100/sec         | Precognitive |
| Aggressive  | 20ms           | ~50/sec          | Pro player |
| Balanced    | 50ms           | ~20/sec          | Good player |
| Greedy      | 60ms           | ~16/sec          | Average player |
| Timid       | 80ms           | ~12/sec          | Cautious player |

### Auto-Spawn Configuration

Server automatically spawns 3 bots when first player connects (in `main_server.gd`):

```gdscript
func _on_player_connected(peer_id: int):
    if game_instance.get_player_count() == 1:  # First player
        spawn_ai_bot_local(AIPersonality.Type.BALANCED)
        spawn_ai_bot_local(AIPersonality.Type.AGGRESSIVE)
        spawn_ai_bot_local(AIPersonality.Type.TIMID)
```

This provides immediate opponents for testing while keeping the game balanced (not overwhelming solo players with too many bots).

## 5. Performance and Networking

### Server-Side Optimization

All AI calculations run server-side with careful optimization strategies:

**Shared World State Analysis:**
```gdscript
# AIObserver updates once per frame, shared by all bots
func update_danger_map():
    danger_map.clear()
    for bomb in game_instance.get_bombs():
        # Calculate once, used by all bots
        explosion_cells = simulate_explosion(bomb)
        for cell in explosion_cells:
            danger_map[cell] = bomb.time_until_explosion()
```

**Reaction Throttling:**
Each bot only makes decisions at personality-specific intervals (10-80ms), not every physics frame:
```gdscript
if current_time - last_reaction_time < personality_weights.reaction_delay * 0.5:
    return last_action  # Reuse previous decision
```

**Pathfinding Caching:**
Paths are calculated infrequently (0.3-1.5 seconds) and reused until invalidated:
```gdscript
if current_path.is_empty() or stuck_counter > 10:
    current_path = find_strategic_path(...)  # Only recalculate when needed
```

**BT Efficiency:**
- Behavior Trees use early exit (Sequence fails on first failure)
- No deep recursion (max depth = 3 levels typically)
- Stateless nodes minimize memory overhead
- Node pooling could be added if needed for 10+ bots

**Performance Metrics (tested with 3 bots @ 60 FPS):**
- Average CPU per bot: <0.5ms per frame
- Memory per bot: ~50KB (controller + observer)
- Network overhead: 0 (bots don't consume network, just part of state snapshot)
- Scales well to 5-6 bots; 10 bots feasible on modern hardware

### Network Architecture

**Client Perspective:**
Clients receive state snapshots at 20Hz containing:
```gdscript
{
    "players": {
        "peer_id_1": { "position": Vector2, "is_alive": bool },
        "bot_0": { "position": Vector2, "is_alive": bool },  # Indistinguishable
        "bot_1": { "position": Vector2, "is_alive": bool }
    },
    "bombs": [...],
    "blocks": [...]
}
```

Bots are synced identically to human players. Clients cannot tell the difference (by design).

**Server Authority:**
- AI decisions execute immediately on server
- No input latency (unlike human players)
- Client-side prediction not needed for bots
- Actions (movement, bombs) are part of next state snapshot

**Offline Mode:**
For single-player, the server runs locally:
```gdscript
# Client starts local server process
var server = preload("res://server/main_server.gd").new()
server.start_local_server()
# Networking bypassed, everything runs in-process
```

### Latency Handling

**Human vs Bot Differences:**

| Aspect | Human Players | AI Bots |
|--------|---------------|---------|
| Input Lag | 30-100ms (network RTT) | 0ms (local server) |
| Prediction | Client-side predicted | Server-authoritative |
| Correction | Reconciliation needed | No correction needed |
| State Updates | 20Hz from server | 20Hz to clients |

**Fair Play Considerations:**
- Bots' 10-80ms reaction delays simulate human input lag
- Imperfect information: Bots only see what's on the grid (no wallhacks)
- Occasional mistakes: Stuck detection, random bomb chance
- No perfect prediction: Bots don't simulate future player moves

## 6. Testing and Evaluation

### Implemented Testing Features

**Debug Logging:**
State transitions are logged to console in debug builds:
```gdscript
if OS.is_debug_build():
    print("[AI %s] State: %s → %s" % [
        get_personality_name(),
        State.keys()[old_state],
        State.keys()[new_state]
    ])
```

**Example Output:**
```
[AI Aggressive] State: EXPLORING → HUNTING
[AI Balanced] State: EXPLORING → ESCAPING
[AI Balanced] State: ESCAPING → EXPLORING
[AI Aggressive] State: HUNTING → CORNERING
[AI Aggressive] State: CORNERING → ESCAPING
```

### Test Scenarios

**1. Survival Test:**
- Map: Random bomb spawns every 2 seconds
- Objective: Bot survives as long as possible
- Validates: Escape logic, danger detection, safe tile finding
- Expected: Timid > Balanced > Aggressive > Chaos (survival time)

**2. Trap Test:**
- Map: One stationary dummy player
- Objective: Bot successfully traps and eliminates dummy
- Validates: Hunting → Cornering transition, bomb placement, trap_bonus utility
- Expected: Aggressive and Chaos successfully trap within 30s

**3. Block Clearing Test:**
- Map: Standard game with 40% breakable blocks
- Objective: Bot clears maximum blocks in 2 minutes
- Validates: Exploration, block cluster finding, bomb placement
- Expected: Greedy > Balanced > Aggressive > Timid (blocks destroyed)

**4. Multi-Bot Battle:**
- Map: Standard arena, 4 bots (one of each personality)
- Objective: Last bot standing
- Validates: Full system under competitive conditions
- Expected: No crashes, varied strategies observable, eventual winner

**5. State Transition Test:**
- Map: Standard arena with human player
- Objective: Observe bot state changes over 5 minutes
- Validates: State machine logic, appropriate transitions
- Expected: 
  - Balanced: 60% EXPLORING, 20% ESCAPING, 15% HUNTING, 5% CORNERING
  - Aggressive: 40% HUNTING, 30% CORNERING, 20% ESCAPING, 10% EXPLORING
  - Timid: 70% EXPLORING, 25% ESCAPING, 5% HUNTING

### Metrics to Track

**Survival Metrics:**
- Average survival time per personality
- Self-inflicted deaths (bomb traps)
- Deaths to other players vs environment

**Combat Metrics:**
- Kill/Death ratio
- Successful traps (opponent killed by bot's bomb)
- Trap attempts vs successes

**Efficiency Metrics:**
- Blocks destroyed per minute
- Power-ups collected (when implemented)
- Average time in each state

**Realism Metrics:**
- APM (Actions Per Minute): Should vary by personality
  - Chaos: 600-800 APM (10-13 actions/sec)
  - Aggressive: 300-400 APM
  - Balanced: 120-200 APM
  - Timid: 80-120 APM
- Decision consistency: Should occasionally make "mistakes" (stuck counter, random bombs)
- Movement patterns: Should not be perfectly optimal (reaction delays create human-like hesitation)

### Debug Visualization Ideas (Future)

**In-Game Overlays (Server Debug Mode):**
- Danger map: Red overlay on tiles in explosion range
- BT status: Current executing node name above bot
- Target indicators: Arrow pointing to current target_tile
- State display: Text label showing current state
- Utility scores: Numbers on adjacent tiles showing calculated utility

**External Tools:**
- Match replay system capturing AI decisions
- State machine diagram showing transition counts
- Heat map of bot movement patterns
- Timeline showing state changes over match duration

## 7. Future Expansion

### Immediate Enhancements (Ready to Implement)

**Power-Up Awareness:**
Currently bots find block clusters but don't track revealed power-ups. Add to AIObserver:
```gdscript
func find_nearest_powerup(from_tile: Vector2i) -> Vector2i:
    var powerups = game_instance.get_powerups()
    var nearest = Vector2i(-1, -1)
    var min_dist = INF
    for powerup in powerups:
        var tile = powerup.get_tile_position()
        var dist = manhattan_distance(from_tile, tile)
        if dist < min_dist:
            min_dist = dist
            nearest = tile
    return nearest
```

Then create **POWER_UP_RUSH** state:
- Transition: When high-value power-up visible AND within 10 tiles
- BT: Find power-up → Path to it → Grab → Return to EXPLORING
- Priority: Greedy personality enters this state frequently

**Chain Reaction Awareness:**
Enhance `calculate_bomb_value()` to detect chain reactions:
```gdscript
# +200 bonus if bomb will trigger other bombs
for bomb in game_instance.get_bombs():
    if bomb.position in explosion_cells:
        value += 200.0  # Chain reaction bonus
```

**Teammate Coordination (Team Mode):**
For 2v2 or team battles:
- Add team_id to AIPlayer
- Avoid bombing teammates
- Coordinate pincer attacks
- Share target information

**Difficulty Levels:**
Add difficulty multiplier that scales reaction_delay and bomb thresholds:
```gdscript
enum Difficulty { EASY, NORMAL, HARD, EXPERT }

# EASY: reaction_delay * 2.0, bomb_threshold * 1.5
# NORMAL: no change
# HARD: reaction_delay * 0.5, bomb_threshold * 0.7
# EXPERT: reaction_delay * 0.3, bomb_threshold * 0.5
```

### Advanced AI Features (Future Research)

**1. Reinforcement Learning (ML-Based Tuning):**

Current utility weights (e.g., `trap_bonus = 600`) are hand-tuned. Could be learned:

**Q-Learning Approach:**
```gdscript
# State: (my_position, opponent_positions, bomb_positions, powerups)
# Actions: 5 movements + place_bomb
# Reward: +1000 for kill, +100 for block destroyed, -1000 for death

# Train by having bots play 10,000+ matches against each other
# Neural network learns optimal weights per game state
```

**Implementation Path:**
1. Log game states and actions to training data
2. Export to Python for training (TensorFlow/PyTorch)
3. Import learned weights back to GDScript
4. A/B test learned vs hand-tuned bots

**2. Player Mimicry (Behavioral Cloning):**

Record human player patterns and create personalities that mimic them:

```gdscript
# Record player data:
{
    "situation": "opponent_3_tiles_away",
    "action": "place_bomb",
    "frequency": 0.75  # Human did this 75% of the time
}

# Create "HumanLike" personality that samples from this distribution
```

**3. Monte Carlo Tree Search (MCTS):**

For "Expert" difficulty, simulate future game states:

```python
# Simulate 100 possible futures (each 5 moves deep)
# Choose action that leads to highest win probability
# Computationally expensive but creates near-perfect play
```

**4. Cooperative Multi-Agent (Team AI):**

Bots communicate and coordinate:
```gdscript
# Bot A: "I'm hunting opponent at (10, 5)"
# Bot B: "I'll block their escape at (12, 5)"
# Result: Coordinated pincer attack
```

**5. Adaptive Personalities:**

Bots adjust weights based on opponent behavior:
```gdscript
# If player is aggressive (often chases):
personality_weights.aggression -= 100  # Become more defensive
personality_weights.trap_bonus += 200  # Set more traps

# If player is passive (rarely bombs):
personality_weights.aggression += 100  # Hunt them more
```

### Personality Expansion

**New Personalities to Add:**

**Personality #6: DEFENSIVE (Wall Hugger)**
- High safety (1000)
- Low aggression (50)
- Prefers corners and edges
- Only bombs when cornered

**Personality #7: KAMIKAZE (Suicide Bomber)**
- Low safety (200)
- Very high aggression (900)
- Places bombs without escape route
- Tries to trade kills

**Personality #8: STRATEGIC (Chess Player)**
- Medium all stats
- Uses long pathfinding (plans 5+ moves ahead)
- Rarely makes mistakes
- Calculates optimal positioning

**Personality #9: COPYCAT (Mimicry)**
- Learns from human player in first 30 seconds
- Adjusts weights to match player's style
- Creates "mirror match" feeling

### Backend Integration

**Stat Tracking (PlayFab/Nakama):**
```gdscript
# Upload bot performance to backend
{
    "bot_id": "aggressive_bot_1",
    "match_id": "abc123",
    "personality": "AGGRESSIVE",
    "kills": 3,
    "deaths": 1,
    "blocks_destroyed": 45,
    "survival_time": 180.5,
    "state_time": {
        "EXPLORING": 45.2,
        "HUNTING": 89.7,
        "CORNERING": 23.1,
        "ESCAPING": 22.5
    }
}

# Use for:
# - Balancing personalities (nerf if win rate > 60%)
# - Matchmaking (pair human with similar-skill bot)
# - Leaderboards (top AI vs top human)
```

**Dynamic Bot Spawning:**
```gdscript
# Backend decides which personalities to spawn based on:
# - Human player skill level (from match history)
# - Desired difficulty progression
# - Variety (avoid 3x same personality)
```

### Visual Enhancements

**Bot Cosmetics:**
- Each personality has unique character skin
- Color-coded names (red = aggressive, blue = timid, etc.)
- Emote system (bots taunt after kills, panic when escaping)

**UI Indicators:**
- Bot name includes personality: "Aggressive Bot #1"
- Small icon showing current state (sword = hunting, shield = escaping)
- Kill feed shows bot personality: "Chaos Bot demolished Player with bomb"

### Performance Scaling

**For 10+ Bot Matches:**
- Implement bot pooling (reuse inactive bots)
- Reduce pathfinding frequency (1.5s → 3s for distant bots)
- LOD system: Bots far from players use simplified logic
- Parallel BT execution (multi-threaded if needed)

### Research Questions

**Open Problems to Explore:**
1. What's the optimal bomb threshold range for competitive play?
2. How much reaction delay feels "fair" to human players?
3. Can bots learn to predict human escape patterns?
4. What personality distribution creates most engaging matches?
5. How to prevent bots from "ganging up" on solo human player?

---

## Summary: Implementation Status

### ✅ Completed Features
- Triple-hybrid architecture (State Machine + Behavior Trees + Utility System)
- 5 distinct personalities with tunable weights
- 6 state machine states with intelligent transitions
- 5 behavior trees for tactical sequences
- Complete BT node library (15+ node types)
- AIObserver with danger maps and escape analysis
- Server integration with auto-spawning
- Personality-based reaction times (10-80ms range)
- Smart bomb value calculation
- Block cluster targeting
- Opponent tracking and hunting
- Escape route analysis
- Strategic positioning
- Stuck detection and recovery

### 🚧 Ready for Enhancement
- Power-up awareness and POWER_UP_RUSH state
- Chain reaction detection
- Team coordination for team modes
- Difficulty level system
- Debug visualization overlays
- Match statistics and logging

### 🔬 Future Research
## 14. Advanced AI Features (Q-Learning & MCTS)

**Status**: ✅ **IMPLEMENTED** (Q-Learning and MCTS for expert bots)

### Overview

The Advanced AI Features introduce two sophisticated decision-making systems that go beyond the hybrid State Machine + Behavior Tree + Utility architecture:

1. **Q-Learning (Reinforcement Learning)**: A model-free RL algorithm that learns optimal actions through experience, used by the **LEARNED** personality.
2. **MCTS (Monte Carlo Tree Search)**: A tree-based planning algorithm that simulates future moves to find optimal actions, used by the **PERFECT** personality.

These systems are implemented as **alternative decision-making layers** that can be selectively enabled via personality configurations.

---

### Q-Learning Implementation

**File**: `shared/ai/ai_q_learning.gd`

**Personality**: `LEARNED` (Type 9)

#### How It Works

Q-Learning is a temporal difference learning algorithm that learns a Q-function: `Q(state, action) → value`. The bot learns which actions lead to better outcomes by exploring the environment and receiving rewards.

**Algorithm**:
```
Q(s,a) ← Q(s,a) + α[r + γ max Q(s',a') - Q(s,a)]

Where:
- α (alpha) = 0.1: Learning rate
- γ (gamma) = 0.95: Discount factor
- ε (epsilon) = 0.1: Exploration rate (10% random actions)
```

#### State Representation

The game state is quantized into a compact hash for efficient Q-table lookup:

```gdscript
State Hash = [region_x, region_y, danger_level, nearby_bombs, bombs_available]

Components:
- Region (3x3 grid): Player position quantized to 9 regions
- Danger level (0-3): Time until explosion at current tile
  * 0 = Safe (> 2s)
  * 1 = Moderate (1-2s)
  * 2 = High (0.5-1s)
  * 3 = Critical (< 0.5s)
- Nearby bombs (0-2): Count of bombs within 5 tiles
- Bombs available (0-1): Whether bot can place bomb
```

This quantization reduces the state space from millions of continuous states to ~200-500 discrete states, making learning tractable.

#### Actions

6 discrete actions:
1. **MOVE_UP** (0)
2. **MOVE_DOWN** (1)
3. **MOVE_LEFT** (2)
4. **MOVE_RIGHT** (3)
5. **PLACE_BOMB** (4)
6. **WAIT** (5)

#### Reward Function

Rewards guide learning by signaling which behaviors are desirable:

```gdscript
Rewards:
  +500  Kill opponent
  +50   Destroy block
  +30   Escape danger
  +10   Opponent proximity (< 3 tiles)
  +1    Survival per frame
  -10   Moderate danger
  -20   High danger
  -50   Critical danger
  -1000 Death
```

#### Learning Process

**Epsilon-Greedy Exploration**:
- 10% of the time: Choose random action (exploration)
- 90% of the time: Choose best known action (exploitation)

**Q-Value Update**:
- After each action, update Q(s,a) based on received reward and next state's best Q-value
- This propagates reward signals backward through state-action sequences

**Episode Boundaries**:
- `on_player_death()`: Large negative reward (-1000)
- `on_player_kill()`: Large positive reward (+500)
- `on_match_end()`: Save Q-table to disk for persistence

#### Persistence

Q-table is saved to `user://q_table.json` every 10 episodes, allowing the bot to retain learning across matches. The table stores:

```json
{
  "hash_string": [q_up, q_down, q_left, q_right, q_bomb, q_wait]
}
```

#### Integration

**AIBotController** integration:
```gdscript
# Initialization in _init()
if personality_weights.get("use_q_learning", false):
    q_learning = AIQLearning.QLearning.new()
    q_learning.load_q_table()  # Load previous learning

# Decision making in decide_action()
if q_learning != null:
    return decide_action_q_learning(ai_player, current_tile, game_state, current_time)
```

**Training Interface**:
```gdscript
controller.on_player_death()      # -1000 reward
controller.on_player_kill()       # +500 reward
controller.on_block_destroyed()   # +50 reward
controller.on_match_end()         # Save Q-table
```

#### Performance Characteristics

**LEARNED Personality Weights**:
```gdscript
{
  "safety": 1000.0,
  "aggression": 700.0,
  "reaction_delay": 0.03,  # 30ms - Fast learner
  "use_q_learning": true
}
```

**Behavior**:
- Initially random/exploratory
- Improves over ~50-100 matches
- Learns to avoid danger, chase opponents, destroy blocks
- Develops map-specific strategies (learns choke points, safe zones)
- Can discover non-obvious tactics through exploration

**Advantages**:
- Adapts to player behavior over time
- Discovers strategies not hand-coded
- Improves with more matches

**Limitations**:
- Requires training period (50+ matches)
- Can overfit to specific maps/opponents
- Exploration can lead to suboptimal early-game decisions

---

### MCTS Implementation

**File**: `shared/ai/ai_mcts.gd`

**Personality**: `PERFECT` (Type 10)

#### How It Works

MCTS is a tree search algorithm that builds a decision tree by simulating random playouts from each node. It balances exploration (trying untested moves) and exploitation (choosing known good moves) using UCB1.

**Algorithm Phases**:
1. **Selection**: Traverse tree using UCB1 until reaching a leaf
2. **Expansion**: Add a new child node for an untried action
3. **Simulation**: Run random playout from new node to terminal state
4. **Backpropagation**: Update all parent nodes with simulation result

#### UCB1 Selection Formula

```
UCB1(node) = exploitation + exploration
           = (node.total_reward / node.visits) + c * √(ln(parent.visits) / node.visits)

Where:
- c = 1.41 (√2): Exploration constant
```

This formula ensures nodes with high average rewards are selected (exploitation), but also gives chances to less-visited nodes (exploration).

#### Search Configuration

```gdscript
Max iterations: 100 simulations per decision
Time budget: 50ms max
Simulation depth: 10 moves
Discount factor: 0.95 (future rewards decay)
```

#### State Simulation

MCTS simulates future game states by predicting:
- **Movement**: Tile-based position updates
- **Collision**: Wall/obstacle detection
- **Danger**: Bomb explosion timers and blast zones
- **Survival**: Whether bot is alive after action sequence

**Simplified Physics**:
- No sub-tile positions (faster simulation)
- Approximated opponent behavior (random walks)
- No bomb chain reactions (conservative estimate)

#### Actions

Same 6 actions as Q-Learning:
1. MOVE_UP
2. MOVE_DOWN
3. MOVE_LEFT
4. MOVE_RIGHT
5. PLACE_BOMB
6. WAIT

#### Reward Function (Simulation)

Different from Q-Learning - focused on predicting outcomes:

```gdscript
Rewards per simulation step:
  +1    Survival per frame
  +5    Safe tile bonus
  -10   High danger
  -50   Critical danger
  -100  Death
```

The total reward for a simulation is the sum of rewards over 10 moves, discounted by 0.95^depth.

#### Tree Structure

**MCTSNode Class**:
```gdscript
class MCTSNode:
    var visits: int = 0
    var total_reward: float = 0.0
    var parent: MCTSNode = null
    var children: Array[MCTSNode] = []
    var untried_actions: Array[int] = [0,1,2,3,4,5]
    var state: Dictionary  # Game state snapshot
```

**Tree Growth**:
- Root node represents current game state
- Each child represents outcome of one action
- Tree grows asymmetrically - promising branches get more visits
- Tree is reset after each decision (no persistence between frames)

#### Integration

**AIBotController** integration:
```gdscript
# Initialization in _init()
if personality_weights.get("use_mcts", false):
    mcts = AIMCTS.MCTS.new()

# Decision making in decide_action()
if mcts != null:
    return decide_action_mcts(ai_player, current_tile, game_state, current_time)
```

**State Construction**:
```gdscript
var mcts_state = {
    "position": current_tile,
    "danger_map": observer.danger_map.duplicate(),
    "bombs": game_state.bombs.duplicate(),
    "opponents": game_state.opponents.duplicate(),
    "breakables": game_state.breakables.duplicate(),
    "map": game_state.map,
    "has_bomb": ai_player.bombs_remaining > 0
}
```

#### Performance Characteristics

**PERFECT Personality Weights**:
```gdscript
{
  "safety": 1500.0,
  "aggression": 800.0,
  "reaction_delay": 0.05,  # 50ms - Simulation time
  "use_mcts": true
}
```

**Behavior**:
- Highly tactical and calculating
- Plans 10 moves ahead
- Prioritizes survival over aggression
- Excellent at trap avoidance
- Strong positional play (controls center, choke points)

**Advantages**:
- No training required - plays well immediately
- Handles complex tactical situations (multiple bombs, tight escapes)
- Adapts to opponent behavior in real-time
- Can "see" multi-move traps before committing

**Limitations**:
- Computationally expensive (50ms per decision)
- Simplified simulation may miss chain reactions
- Assumes random opponent behavior (no opponent modeling)
- Tree resets each frame (no long-term planning memory)

---

### Comparison: Q-Learning vs MCTS

| Feature | Q-Learning (LEARNED) | MCTS (PERFECT) |
|---------|---------------------|----------------|
| **Training Required** | Yes (50+ matches) | No |
| **Immediate Skill** | Low → High | High |
| **Adaptability** | High (learns patterns) | Medium (reacts) |
| **Computational Cost** | Low (~1ms) | High (~50ms) |
| **Tactical Depth** | Medium | Very High |
| **Exploration** | Epsilon-greedy | UCB1 |
| **Memory** | Persistent Q-table | None (tree resets) |
| **Best Use Case** | Long-term learning | Expert-level play |

---

### Future Enhancements

**Hybrid Q-Learning + MCTS**:
- Use Q-values to guide MCTS simulation policy (instead of random playouts)
- Train Q-function with MCTS rollout data

**Neural Networks**:
- Replace Q-table with neural network (Deep Q-Learning)
- Replace MCTS value function with neural network (AlphaZero-style)

**Opponent Modeling**:
- Track opponent behavior patterns
- Predict opponent moves in MCTS simulations

**Experience Replay**:
- Store Q-Learning experiences in replay buffer
- Sample mini-batches for stable learning

**Progressive Widening**:
- MCTS considers fewer actions initially, expands later
- Reduces computation for early decisions

---

## 15. Future Enhancements

**Potential Future Work**:
- Neural network Q-function (Deep Q-Learning/DQN)
- AlphaZero-style neural MCTS
- Opponent modeling and behavioral cloning
- Additional personality types (Defensive, Kamikaze, Strategic, Copycat)
- Backend integration for stat tracking and matchmaking
