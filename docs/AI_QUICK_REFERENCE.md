# AI System Quick Reference

## Toggle AI Systems

```gdscript
# In ai_player.gd
var use_improved_ai: bool = true   # ✨ NEW intelligent AI (default)
var use_improved_ai: bool = false  # Legacy behavior tree AI
```

## Key Classes

| Class | Purpose | Location |
|-------|---------|----------|
| `ImprovedAIController` | Main decision loop | `shared/ai/improved_ai_controller.gd` |
| `DangerMapper` | Bomb danger tracking | `shared/ai/danger_mapper.gd` |
| `UtilityScorer` | Action evaluation | `shared/ai/utility_scorer.gd` |
| `BombPlanner` | Safe bomb placement | `shared/ai/bomb_planner.gd` |
| `AIDebugVisualizer` | Visual debugging | `shared/ai/ai_debug_visualizer.gd` |
| `PlayerLogManager` | Data logging | `shared/ai/player_log_manager.gd` |

## Action Priority (Utility Scores)

```
2000 - Emergency escape (< 0.5s to explosion)
1500 - Urgent escape (< 1.0s to explosion)
1000 - High danger escape (< 1.5s to explosion)
  25 - Attack opportunity (trap + kill)
  20 - Chain bomb setup
  15 - Attack player (close range)
  10 - Destroy blocks (per block)
   8 - Collect power-up
   5 - Reposition strategic
   3 - Random patrol
```

## Safety Checks (Bomb Placement)

```gdscript
✅ Bomb available?
✅ Tile walkable?
✅ No existing bomb?
✅ Escape route exists?
✅ Escape reachable in time?
   time_to_safety + 0.5s < BOMB_TIMER
```

## Debug Visualization Colors

| Color | Meaning |
|-------|---------|
| 🔴 Red | Critical danger (< 0.5s) |
| 🟠 Orange | Medium danger (0.5-1.5s) |
| 🟡 Yellow | Low danger (1.5-2.5s) |
| 🟢 Green | Safe |
| 🔵 Blue | AI path |
| 🟣 Magenta | Target position |

## Performance Settings

```gdscript
decision_interval = 0.1      # 10 decisions/sec
danger_update_interval = 0.05  # 20 updates/sec
path_update_interval = 0.3   # 3 paths/sec
astar_rebuild_interval = 0.5  # 2 rebuilds/sec
```

## Player Logging

```gdscript
# Start logging
var logger = PlayerLogManager.new(game_instance)
logger.start_session("match_001")

# Track players
logger.track_player(player_node, "p1", "PlayerName")

# Update every frame
func _process(delta):
    logger.update(delta)

# End and save
logger.end_session()
logger.export_to_csv()  # For ML training
```

## Log Output Locations

```
JSON: user://player_logs/session_YYYYMMDD_HHMMSS.json
CSV:  user://player_logs/session_YYYYMMDD_HHMMSS.csv

# Actual path (Linux):
~/.local/share/godot/app_userdata/Bomberman/player_logs/
```

## Common Issues & Fixes

### AI Doesn't Move
**Check**: Is danger_mapper updating?  
**Fix**: Call `danger_mapper.update(current_time)` each frame

### AI Suicides
**Check**: Is BombPlanner being used?  
**Fix**: Verify `bomb_planner.can_place_bomb_safely()` returns true

### Visualizer Not Showing
**Check**: Is debug build?  
**Fix**: Set `debug_visualizer.enabled = true` manually

### A* Path Broken
**Check**: Is astar graph rebuilt?  
**Fix**: Call `_ensure_astar_ready(current_time)` before pathfinding

## Personality Behavior Matrix

| Personality | Aggression | Escape Threshold | Trap Bonus | Chain Bonus |
|-------------|------------|------------------|------------|-------------|
| KAMIKAZE | High (1000) | 0.3s | Low | Low |
| DEFENSIVE | Low (200) | 2.5s | Medium | Low |
| TRAPPER | Medium (500) | 1.5s | High (800) | Medium |
| STRATEGIC | Medium (500) | 1.5s | Medium | High (1000) |
| GREEDY | Medium (500) | 1.5s | Medium | Low |
| BALANCED | Medium (500) | 1.5s | Medium | Medium |

## Testing Commands

```bash
# Run server with AI bots
./start-server-test.sh

# Check AI status
tail -f ~/.local/share/godot/logs/godot.log | grep "ImprovedAI"

# View player logs
cat ~/.local/share/godot/app_userdata/Bomberman/player_logs/session_*.json | jq '.total_frames'
```

## Integration Checklist

- [x] DangerMapper created
- [x] UtilityScorer created
- [x] BombPlanner created
- [x] ImprovedAIController created
- [x] AIDebugVisualizer created
- [x] PlayerLogManager created
- [x] AIPlayer updated to use ImprovedAIController
- [ ] Test suicide prevention
- [ ] Test emergency escapes
- [ ] Test player data logging
- [ ] Tune personality behaviors

## Next Steps

1. **Test the AI**: Spawn multiple bots and verify behavior
2. **Enable Logging**: Track human player data for training
3. **Tune Parameters**: Adjust scores and thresholds
4. **Train ML Model**: Use logged data for imitation learning
5. **Deploy**: Replace legacy AI with improved system

---

**Quick Toggle AI**:
```gdscript
# In shared/entities/ai_player.gd line 7:
var use_improved_ai: bool = true  # ← Set this
```

**Quick Enable Debug**:
```gdscript
# In shared/ai/ai_debug_visualizer.gd __init():
enabled = true  # Force enable even in release builds
```

**Quick Start Logging**:
```gdscript
# In server/game_instance.gd _ready():
player_logger = PlayerLogManager.new(self)
player_logger.start_session()
```

---

**Status**: ✅ System Complete - Ready for Testing
