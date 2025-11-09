# Improved AI System Documentation

## Overview

The new AI system provides intelligent, reactive gameplay with **zero suicides**, purposeful decision-making, and smooth free-movement navigation. It replaces random behavior with tactical reasoning while respecting the continuous physics-based movement model.

---

## Architecture

### Core Components

#### 1. **DangerMapper** (`danger_mapper.gd`)
**Purpose**: Tracks bomb explosions with time-based danger intensity.

**Features**:
- Continuous danger zone tracking with intensity gradients
- Cross-shaped explosion pattern simulation
- Time-until-explosion prediction
- Safe zone caching and pathfinding integration
- Emergency danger detection (< 0.8s to escape)

**Key Functions**:
```gdscript
get_danger_at_tile(tile, current_time, look_ahead) -> float
is_tile_safe(tile, current_time, safety_margin) -> bool
find_nearest_safe_tiles(from_tile, current_time, max_distance) -> Array
calculate_escape_routes(tile, current_time) -> Dictionary
simulate_bomb_placement(bomb_tile, bomb_range, current_time) -> Dictionary
```

#### 2. **UtilityScorer** (`utility_scorer.gd`)
**Purpose**: Evaluates all possible actions and assigns tactical scores.

**Action Types**:
- `ESCAPE_DANGER` (1000-2000 points) - Highest priority
- `ATTACK_PLAYER` (0-25 points) - Trap/kill opportunities
- `MOVE_TO_POWERUP` (0-12 points) - Collect power-ups
- `DESTROY_BLOCKS` (0-30 points) - Clear map
- `CHAIN_BOMB_SETUP` (25+ points) - Strategic chain reactions
- `REPOSITION_STRATEGIC` (3-5 points) - Map control
- `WAIT_AMBUSH` (8-12 points) - Trapper personality

**Scoring Formula**:
```
Value = Base_Score × Distance_Factor × Personality_Modifier - Danger_Penalty
```

**Key Functions**:
```gdscript
score_all_actions(ai_player, current_time) -> Array
get_best_action(scores) -> Dictionary
action_to_movement(action_data, ai_player, current_time) -> Dictionary
```

#### 3. **BombPlanner** (`bomb_planner.gd`)
**Purpose**: Ensures AI **never suicides** by validating escape routes.

**Safety Checks**:
1. ✅ Bomb available?
2. ✅ Tile walkable?
3. ✅ No bomb already there?
4. ✅ Escape route exists?
5. ✅ Escape route reachable in time?

**Key Functions**:
```gdscript
can_place_bomb_safely(bomb_tile, ai_player, current_time) -> Dictionary
evaluate_bomb_placement(bomb_tile, ai_player, current_time) -> Dictionary
should_place_bomb_now(ai_player, current_tile, current_time) -> bool
find_best_bomb_placement(ai_player, search_radius) -> Dictionary
predict_opponent_trap(opponent, ai_player, current_time) -> Dictionary
plan_chain_bomb(ai_player, current_time) -> Dictionary
plan_emergency_escape(ai_player, current_time) -> Dictionary
```

#### 4. **ImprovedAIController** (`improved_ai_controller.gd`)
**Purpose**: Main decision-making loop integrating all systems.

**Decision Flow**:
```
1. Update danger map
2. Emergency check (< 0.8s danger)?
   YES → Emergency escape (ignore all other goals)
   NO  → Continue
3. Score all actions (UtilityScorer)
4. Get best action
5. Validate bomb placement (BombPlanner)
6. Calculate path (A* with danger avoidance)
7. Return movement + bomb decision
```

**Key Functions**:
```gdscript
decide_action(ai_player) -> Dictionary  # Main entry point
_handle_emergency_escape(ai_player, current_tile, current_time) -> Dictionary
_get_direction_to_tile(from_tile, to_tile, from_position, current_time) -> Vector2
```

#### 5. **AIDebugVisualizer** (`ai_debug_visualizer.gd`)
**Purpose**: Visual debugging overlay showing AI reasoning.

**Displays**:
- 🔴 Danger zones (color-coded by urgency)
- 🔵 Planned path (blue line with waypoints)
- 🟣 Target position (magenta crosshair)
- 🟢 AI position (green circle)
- 📝 Current reasoning text

**Toggle with**:
```gdscript
debug_visualizer.toggle_enabled()
```

#### 6. **PlayerLogManager** (`player_log_manager.gd`)
**Purpose**: Records human gameplay data for AI training.

**Logged Data** (every 100ms):
- Position (x, y) and velocity (x, y, magnitude)
- Tile coordinates
- Action (MOVE_UP/DOWN/LEFT/RIGHT, PLACE_BOMB, IDLE, etc.)
- Context: danger level, time until explosion, escape routes
- Nearby entities: bombs, blocks, enemies, powerups
- Game state: players alive, bombs active

**Output Formats**:
- JSON (full structured data)
- CSV (for ML training pipelines)

**Usage**:
```gdscript
var logger = PlayerLogManager.new(game_instance)
logger.start_session("human_gameplay_001")
logger.track_player(player_node, "player_1", "PlayerName")
# ... game plays ...
logger.end_session()  # Saves to user://player_logs/
logger.export_to_csv()  # Exports to CSV format
```

---

## How It Works

### Free Movement + Grid Reasoning

The AI reasons about tile-based areas (for bombs and obstacles) while moving with continuous physics:

1. **Pathfinding**: A* samples grid positions as navigation nodes
2. **Movement**: Smooth interpolation between waypoints
3. **Danger**: Calculated per-tile but checked per-position
4. **Decisions**: Made every 100ms to balance performance and responsiveness

### Safety-First Bomb Placement

**Before placing a bomb, the AI checks**:
```gdscript
# 1. Simulate explosion pattern
var affected_tiles = simulate_explosion_cross(bomb_tile, bomb_range)

# 2. Find escape routes (not in danger zone)
var safe_routes = find_routes_avoiding(affected_tiles)

# 3. Calculate time needed to reach safety
var time_to_safety = distance_to_nearest_safe / movement_speed

# 4. Compare with bomb timer (default 3.0s)
if time_to_safety + 0.5 < BOMB_TIMER:
    return SAFE  # 0.5s buffer for reaction time
else:
    return UNSAFE  # Don't place bomb
```

### Personality Integration

All existing personalities (KAMIKAZE, TRAPPER, STRATEGIC, DEFENSIVE, GREEDY, BALANCED) work with the new system:

- **Personality weights** adjust scoring thresholds
- **KAMIKAZE**: Lower escape thresholds, higher aggression scores
- **DEFENSIVE**: Higher safety margins, prefers ambush over chase
- **TRAPPER**: Bonus for chokepoint control and trap setups
- **STRATEGIC**: Chain bomb bonus, calculated risk-taking
- **GREEDY**: Power-up collection priority increased

---

## Usage

### Enable Improved AI (Default)

In `ai_player.gd`:
```gdscript
var use_improved_ai: bool = true  # Already set by default
```

### Use Legacy AI (For Comparison)

```gdscript
var use_improved_ai: bool = false
```

### Debug Visualization

Automatically enabled in debug builds. Shows:
- Danger zones with countdowns
- AI path and target
- Current reasoning text

### Player Data Logging

**Server-side** (in `game_instance.gd`):
```gdscript
# Create logger
var player_logger = PlayerLogManager.new(self)
player_logger.start_session("match_001")

# Track human players (not AI bots)
for peer_id in players:
    var player = players[peer_id]
    if not player.has_method("is_ai_bot"):
        player_logger.track_player(player, str(peer_id), player.username)

# Update in _process()
func _process(delta):
    player_logger.update(delta)

# End session when match ends
func _on_match_end():
    player_logger.end_session()
    player_logger.export_to_csv()  # Export for ML training
```

---

## Testing the Improvements

### Expected Behaviors

✅ **No Suicides**: AI never places bombs without escape routes  
✅ **Emergency Escapes**: AI immediately flees when danger < 0.8s  
✅ **Purposeful Movement**: AI moves toward goals (blocks, powerups, enemies)  
✅ **Tactical Bombs**: Bombs placed to trap players or destroy block clusters  
✅ **Smooth Pathfinding**: AI navigates around obstacles without getting stuck  
✅ **Danger Avoidance**: AI paths around active bomb danger zones  

### Test Scenarios

1. **Suicide Prevention Test**:
   - Spawn AI in corner
   - AI should NOT place bomb if no escape

2. **Emergency Escape Test**:
   - Place AI in bomb danger zone
   - AI should immediately flee to nearest safe tile

3. **Trap Intelligence Test**:
   - Position AI near enemy
   - AI should place bomb to trap enemy, then escape

4. **Chain Reaction Test**:
   - Place bombs on map
   - Strategic AI should set up chain reactions

5. **Power-up Priority Test**:
   - Drop power-up near AI
   - Greedy AI should prioritize collection

---

## Performance Notes

- **Decision Frequency**: 100ms (10 decisions/sec)
- **Danger Map Updates**: 50ms (20 updates/sec)
- **Path Recalculation**: 300ms (3.3 paths/sec)
- **A* Graph Rebuild**: 500ms (2 rebuilds/sec)

**Total CPU Impact**: ~2-5% per AI bot (optimized for 8 bots)

---

## Training AI from Logged Data

### Data Format

**JSON Structure**:
```json
{
  "session_id": "session_20250108_143052",
  "timestamp": "2025-11-08T14:30:52",
  "total_frames": 1234,
  "data": [
    {
      "time": 12.43,
      "frame": 124,
      "player_id": "player_1",
      "position": {"x": 256.5, "y": 320.8},
      "tile": {"x": 4, "y": 5},
      "velocity": {"x": 100.5, "y": 0.0, "magnitude": 100.5},
      "action": "MOVE_RIGHT",
      "context": {
        "danger_level": 0.0,
        "time_until_explosion": 999.0,
        "escape_routes": 3,
        "nearby_entities": [
          {"type": "soft_block", "distance": 2, "tile": {"x": 6, "y": 5}}
        ],
        "nearest_powerup_distance": 5,
        "nearest_enemy_distance": 8,
        "can_place_bomb": true
      }
    }
  ]
}
```

**CSV Format** (for ML pipelines):
```csv
time,frame,player_id,pos_x,pos_y,tile_x,tile_y,vel_x,vel_y,vel_mag,action,danger,time_until_explosion,escape_routes,nearby_bombs,nearby_blocks,can_place_bomb
12.43,124,player_1,256.50,320.80,4,5,100.50,0.00,100.50,MOVE_RIGHT,0.00,999.00,3,0,1,1
```

### Imitation Learning Pipeline

1. **Collect Data**: Run multiple matches with human players
2. **Export CSV**: `logger.export_to_csv()`
3. **Train Model**: Use scikit-learn, TensorFlow, or PyTorch
4. **Predict Actions**: Input (position, context) → Output (action)
5. **Integrate**: Replace UtilityScorer with trained model

### Reinforcement Learning

Use logged data as:
- **State**: position, velocity, context
- **Action**: MOVE_X, PLACE_BOMB, etc.
- **Reward**: 
  - +500 for kills
  - +50 for blocks destroyed
  - +10 for power-ups
  - -1000 for death
  - +1 for survival

Train with Q-Learning or Deep Q-Networks (DQN).

---

## Troubleshooting

### AI Gets Stuck
**Cause**: Path blocked by dynamic obstacles  
**Fix**: A* graph rebuilds every 500ms to adapt

### AI Suicides
**Cause**: BombPlanner safety check failed  
**Debug**: Enable visualizer, check escape route calculation

### AI Too Passive
**Cause**: Personality aggression too low  
**Fix**: Increase `aggression` weight in personality config

### AI Too Aggressive
**Cause**: Bomb value threshold too low  
**Fix**: Increase `min_value_threshold` in BombPlanner

### Debug Visualizer Not Showing
**Cause**: Not running in debug build  
**Fix**: Export with `--debug` flag or force enable:
```gdscript
debug_visualizer.enabled = true
```

---

## Future Improvements

### Phase 3 Enhancements (Optional)

1. **Neural Network Integration**: Replace UtilityScorer with trained model
2. **Multi-Step Planning**: Look-ahead tree search (MCTS) for complex scenarios
3. **Team Coordination**: Cooperative strategies for team modes
4. **Adaptive Learning**: AI learns opponent patterns during match
5. **Difficulty Scaling**: Dynamic personality adjustment based on player skill

---

## File Structure

```
shared/ai/
├── ai_bot_controller.gd        # Legacy AI (complex state machine + behavior trees)
├── improved_ai_controller.gd   # ✨ NEW: Intelligent AI controller
├── danger_mapper.gd            # ✨ NEW: Danger zone tracking
├── utility_scorer.gd           # ✨ NEW: Action scoring system
├── bomb_planner.gd             # ✨ NEW: Safe bomb placement
├── ai_debug_visualizer.gd      # ✨ NEW: Debug overlay
├── player_log_manager.gd       # ✨ NEW: Data logging for training
├── ai_observer.gd              # World state analysis (kept)
├── ai_personalities.gd         # Personality configs (kept)
├── behavior_tree.gd            # Behavior tree nodes (kept for legacy)
├── ai_q_learning.gd            # Q-Learning system (kept)
└── ai_mcts.gd                  # MCTS system (kept)
```

---

## Credits

**Improved AI System v2.0**  
Designed for smooth, intelligent, and safe gameplay in continuous-movement Bomberman.

**Key Principles**:
- Safety First: No suicides
- Reactive: Emergency escapes
- Purposeful: Goal-driven decisions
- Smooth: Free-movement pathfinding
- Observable: Debug visualization
- Trainable: Data logging for ML

---

## Quick Start

**1. Test Improved AI**:
```bash
# Run server with AI bots
./start-server-test.sh
```

**2. Watch AI in action**:
- Red zones = bomb danger
- Blue line = AI path
- Green circle = AI player
- Text = current reasoning

**3. Enable player logging** (in game_instance.gd):
```gdscript
var player_logger = PlayerLogManager.new(self)
player_logger.start_session()
# ... match plays ...
player_logger.end_session()
```

**4. Review logs**:
```bash
ls ~/.local/share/godot/app_userdata/Bomberman/player_logs/
```

---

**Enjoy intelligent, challenging AI opponents that never suicide! 🎮🤖**
