# Utility Function - Quick Reference

## Formula

```
Utility = (Reward * P_Success) - (Risk * P_Failure)
```

## Actions

| Action | Reward | P_Success Formula | Use Case |
|--------|--------|-------------------|----------|
| **get_powerup** | 100 (Fire-Up)<br>80 (Bomb-Up)<br>70 (Speed-Up) | `1.0 - (my_time / enemy_time)` | Race to powerup |
| **kick_snipe** | 400 | `(1.0 / distance) * (1.0 - panic_rating)` | Kill opponent |
| **bait_panic** | 500 | `panic_rating * 0.8` | Trigger enemy suicide |
| **nuisance_bomb** | 10 | 0.99 | Harass (different quadrant) |
| **establish_territory** | 5 | 0.99 | Safe farming |

**Risk:** `-500` (death penalty)

**P_Failure:** `1.0 - can_safely_plant_bomb()` (death risk)

---

## Integration

```gdscript
# bot_controller.gd
var utility_scorer: UtilityScorer

func configure(...):
    utility_scorer = UtilityScorer.new()
    call_deferred("_configure_utility_scorer")

func _score_behavior(child, blackboard):
    if utility_scorer != null:
        var result = utility_scorer.select_best_action(...)
        var action = result["action"]
        var utility = result["utility"]
        
        # Map action → behavior tree node
        if action == "get_powerup" and child == _collect_sequence:
            return base + utility
        # ... etc
```

---

## Example Decision

**Situation:**
- Fire-Up 2 tiles away
- Enemy 5 tiles away
- Safe position (`can_place_bomb = 0.9`)

**Calculation:**
```
get_powerup:
  my_time = 400ms, enemy_time = 1000ms
  P_Success = 1.0 - (400/1000) = 0.6
  P_Failure = 0.1
  Utility = (100 * 0.6) - (-500 * 0.1) = 110.0 ✅

establish_territory:
  P_Success = 0.99
  P_Failure = 0.1
  Utility = (5 * 0.99) - (-500 * 0.1) = 54.95 ❌
```

**Decision:** Get powerup (highest utility)

---

## Files

- `shared/ai/decision/utility_scorer.gd` - Mathematical scorer
- `server/ai/bot_controller.gd` - Integration in _score_behavior
- `docs/UTILITY_FUNCTION_IMPLEMENTATION.md` - Full documentation
- `server/test_utility_scorer.gd` - Unit tests

---

## Testing

```bash
cd /home/elgan/bomberman/server
godot --headless --script test_utility_scorer.gd
# All tests PASSED ✅
```

---

## Status: ✅ COMPLETE
