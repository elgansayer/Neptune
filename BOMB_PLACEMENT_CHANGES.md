# Bomb Placement Logic Improvements

**Date:** November 11, 2025  
**Issue:** AI bots were not planting bombs - they would spawn and stand idle even when safe to bomb

## Root Causes Identified

1. **Overly Conservative Safety Checks**
   - Required time buffer was too large (0.8-0.25s)
   - Escape route analysis was rejecting valid escape paths
   
2. **Low Bombing Frequency**
   - Wandering state only attempted bombing 30% of the time
   - Hunting state required multiple conditions + random roll
   - Power-up collection only bombed when directly blocked

3. **Movement Commitment Too Short**
   - Base recovery commitment was 0.25s (15 frames)
   - No post-bomb escape commitment - bots would immediately change direction

## Changes Made

### 1. Movement Commitment Adjustments

**File:** `shared/entities/server_player.gd`

```gdscript
# Before
const RECOVERY_DURATION := 15  # ~0.25s

# After
const RECOVERY_DURATION := 9  # ~0.15s (reduced general recovery)
const POST_BOMB_ESCAPE_DURATION := 15  # ~0.25s (new: post-bomb escape)
```

**File:** `server/game_instance.gd`

```gdscript
# After placing bomb, commit to escape direction
if escape_dir.length() >= 0.1:
    player.recovery_direction = escape_dir
    player.recovery_frames_remaining = ServerPlayer.POST_BOMB_ESCAPE_DURATION
    player.set_meta("force_replan", true)
```

### 2. Bomb Placement Frequency Increases

**File:** `shared/ai/improved_ai_controller.gd`

#### Wandering State
```gdscript
# Before: 30% chance
if ai_player.can_place_bomb() and randf() < 0.3:

# After: 80% chance
if ai_player.can_place_bomb() and randf() < 0.8:
```

#### Hunting State
```gdscript
# Before: Required distance ≤3 AND random roll
if target_distance <= 3 and ai_player.can_place_bomb():
    # ... safety checks ...
    if targets_player and randf() < bomb_frequency:
        should_bomb = true

# After: Distance ≤4 and deterministic (no random roll)
if target_distance <= 4 and ai_player.can_place_bomb():
    # ... safety checks ...
    if targets_player:
        should_bomb = true
```

#### Power-up Collection State
```gdscript
# Before: Only bombs if next tile is blocked

# After: Checks next tile AND adjacent soft blocks
var has_obstacle = false
if observer._is_tile_valid(next_tile) and not observer._is_tile_walkable(next_tile):
    has_obstacle = true
# Also check adjacent tiles for soft blocks worth clearing
if not has_obstacle:
    for check_dir in [Vector2i.UP, Vector2i.DOWN, Vector2i.LEFT, Vector2i.RIGHT]:
        var check_tile = current_tile + check_dir
        if game_instance.game_map[check_tile.y][check_tile.x] == 2:  # Soft block
            has_obstacle = true
            break
```

### 3. Safety Buffer Reductions

**File:** `shared/ai/bomb_planner.gd`

```gdscript
# Before
var required_time_buffer = lerp(0.8, 0.25, personality_weights.get("aggression_normalized", 0.5))

# After  
var required_time_buffer = lerp(0.5, 0.15, personality_weights.get("aggression_normalized", 0.5))
```

**Impact:**
- Balanced personality: 0.8s → 0.5s buffer required
- Aggressive personality: 0.25s → 0.15s buffer required

### 4. Diagnostic Logging Added

Added logging throughout bomb decision pipeline:

```gdscript
# Wandering bomb attempts
print("[AI-WANDER-BOMB] Checking safety at ", current_tile, " safe:", bomb_safety.safe, " reason:", bomb_safety.get("reason", "unknown"), " can_place:", ai_player.can_place_bomb())

# Successful safety checks
print("[BombPlanner] SAFE to bomb at ", bomb_tile, " escape_time:", time_needed, " buffer:", bomb_timer - time_needed)

# Failed escape route analysis
print("[BombPlanner] No escape routes at ", bomb_tile, " checked dirs:", escape_analysis.all_routes.size())
```

## Results

### Before Changes
- ❌ Bots stood idle at spawn
- ❌ Zero bombs planted in 5+ minute test runs
- ❌ No movement commitment after (theoretical) bomb placement

### After Changes
- ✅ Bots actively plant bombs in wandering, hunting, and collection states
- ✅ Post-bomb escape commitment working: bots move away for 0.25s after planting
- ✅ Reduced recovery commitment (0.15s) allows more responsive turning
- ✅ Test suite validates bomb placement and destruction

### Test Results
```
[PASS] test_bomb_softblock.gd - AI plants bomb and destroys soft block
[Game] Bomb placed by Balanced_Bot_944 at tile (2, 2)
[Game] Balanced_Bot_944 committing escape dir (0.0, -1.0) for 15 frames
[Game] Destroying block at (3, 2)
```

## Behavioral Impact

### Balanced Personality (personality=0)
- Wander bombs: 80% attempt rate when safe
- Safety buffer: ~0.35s (moderate)
- Hunts players within 4 tiles
- Bombs through soft blocks to reach power-ups

### Aggressive Personality (personality=1)
- Wander bombs: 80% attempt rate when safe
- Safety buffer: ~0.15s (minimal)
- More willing to trap players even with tighter margins
- Deterministic bombing when target in range

### Timid Personality (personality=2)
- Wander bombs: 80% attempt rate when safe
- Safety buffer: ~0.5s (maximum)
- Avoids risky bomb placements
- Prioritizes safety over aggression

## Future Improvements

1. **Escape Route Analysis**: Current logic may still be too conservative in tight spaces
2. **Chain Reaction Awareness**: Bots should better predict multi-bomb scenarios
3. **Personality-Based Frequencies**: Consider reducing wander bomb rate for Timid personality
4. **Adaptive Safety**: Adjust safety buffers based on game state (losing = more aggressive)

## Testing

Run automated test suite:
```bash
./bomberman-cli.py test
```

Run live server with bots:
```bash
# Terminal 1: Start server
./bomberman-cli.py server

# Terminal 2: Start client and observe
./bomberman-cli.py client
```

Check logs for bomb placement:
```bash
grep -E '\[Game\] Bomb placed|\[AI-WANDER-BOMB\]' server.log
```
