# 🔥 Explosion Center Tile Bug Fix

**Date:** November 25, 2025  
**Severity:** CRITICAL  
**Status:** ✅ FIXED

---

## 🐛 The Bug

**Problem:** Bots and players standing directly on top of bombs were NOT dying when the bombs exploded.

### Root Cause

The progressive explosion system in `server_bomb.gd` had a critical off-by-one error:

```gdscript
# BEFORE (BROKEN):
func expand_explosion():
    current_explosion_length += 1  # Increment FIRST
    
    if current_explosion_length > explosion_range:
        queue_free()
        return
    
    var tiles_this_frame: Array[Vector2i] = []
    for dir_data in explosion_directions:
        if current_explosion_length <= dir_data["max_length"]:
            var fire_pos = tile_pos + offset * current_explosion_length
            tiles_this_frame.append(fire_pos)  # Only emits length 1, 2, 3...
    
    emit_signal("explosion_expanded", tiles_this_frame)
```

**The Problem:**
1. `current_explosion_length` starts at 0 when bomb explodes
2. Function immediately increments it to 1
3. Then emits tiles at distance 1, 2, 3, etc.
4. **THE CENTER TILE (distance 0) IS NEVER EMITTED!**

### Impact

- Players standing on the bomb itself were invulnerable
- Bots would plant bombs and stand on them without dying
- Made suicide prevention system irrelevant since suicides were impossible anyway
- Completely broke game balance

---

## ✅ The Fix

### Solution

Emit tiles **BEFORE** incrementing the length counter, and handle center tile (length 0) explicitly:

```gdscript
# AFTER (FIXED):
func expand_explosion():
    # Get tiles at current expansion length BEFORE incrementing
    var tile_pos = get_tile_position()
    var tiles_this_frame: Array[Vector2i] = []
    
    # Handle center tile (length 0) on first expansion
    if current_explosion_length == 0:
        tiles_this_frame.append(tile_pos)  # ✅ Emit center tile!
    else:
        # Handle directional expansion
        for dir_data in explosion_directions:
            if current_explosion_length <= dir_data["max_length"]:
                var offset = dir_data["offset"]
                var fire_pos = tile_pos + offset * current_explosion_length
                tiles_this_frame.append(fire_pos)
    
    # Emit signal for GameInstance to handle damage/destruction
    if tiles_this_frame.size() > 0:
        emit_signal("explosion_expanded", tiles_this_frame)
    
    # Increment for next frame
    current_explosion_length += 1
    
    if current_explosion_length > explosion_range:
        await get_tree().create_timer(0.5).timeout
        queue_free()
        return
```

### Additional Fix

Added dead player check to prevent double-kills:

```gdscript
# In game_instance.gd::_on_explosion_expanded()
for peer_id in players:
    var player = players[peer_id]
    
    # Skip dead players - they cannot be killed again
    if player.is_dead:
        continue
    
    # ... rest of explosion damage logic
```

---

## 📊 Verification

### Before Fix:
```
[ServerBomb] Timer reached limit! Calling explode(). ID: 0
[Game] Bomb exploded: 0 with 5 tiles
# NO DEATH MESSAGES - players standing on bombs were invulnerable!
```

### After Fix:
```
[ServerBomb] Timer reached limit! Calling explode(). ID: 0
[ServerBomb] Expanding to center tile: (16, 2)
[Game] Player Balanced_Bot_1 killed by explosion at (16, 2)  ✅
[ServerBomb] Emitted 1 explosion tiles at length 0
[ServerBomb] Emitted 3 explosion tiles at length 1
[ServerBomb] Emitted 1 explosion tiles at length 2
```

---

## 🎯 Impact

### What Now Works:
✅ Players/bots standing on bombs are killed when they explode  
✅ Suicide prevention system is actually necessary and effective  
✅ Explosion expands correctly: center (length 0) → adjacent (length 1) → range 2, etc.  
✅ Game balance restored - bombs are dangerous again  

### Files Modified:
1. **`shared/entities/server_bomb.gd`**
   - Fixed `expand_explosion()` to emit center tile first
   - Moved increment after tile emission

2. **`game_instance.gd`**
   - Added `is_dead` check to prevent double-kills
   - Clean explosion damage logic

---

## 🔍 Testing

### Manual Test:
```bash
timeout 30s ./bomberman both 2>&1 | grep "killed by explosion"
```

**Expected Output:**
```
[Game] Player Bot_1 killed by explosion at (X, Y)
[Game] Player Bot_2 killed by explosion at (X, Y)
...
```

### Validation:
- ✅ Bots die when standing on their own bombs
- ✅ Bots die when standing on other players' bombs
- ✅ Explosions expand progressively (center → edges)
- ✅ No duplicate death messages
- ✅ Match ends correctly when all but one player dies

---

## 💡 Lessons Learned

1. **Off-by-one errors are deadly** - especially in explosion systems
2. **Test center tile explicitly** - it's the most common scenario (suicide)
3. **Progressive systems need careful ordering** - increment/emit order matters
4. **Log early, log often** - debug output revealed the issue immediately

---

## 📝 Related Issues

- Suicide prevention (now actually necessary): `SUICIDE_PREVENTION_SUMMARY.md`
- Bomb explosion system: `shared/entities/server_bomb.gd`
- Player death handling: `shared/entities/server_player.gd`

---

**Status:** ✅ COMPLETE - Explosions now correctly damage all tiles including center
