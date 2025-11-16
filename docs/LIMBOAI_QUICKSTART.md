# LimboAI Refactoring - Quick Start Guide

This document provides a quick reference for implementing the LimboAI refactoring in Neptune-Bomberman.

## 🎯 Overview

**Goal**: Refactor Neptune-Bomberman's game logic from custom Behavior Trees to LimboAI while maintaining the authoritative server architecture.

**Why LimboAI?**
- ✅ Visual BT editor with debugging
- ✅ Industry-standard implementation
- ✅ Better performance (C++ GDExtension)
- ✅ Easier to maintain and modify
- ✅ Built-in documentation

## 📚 Documentation Index

### 1. Installation Guide
**File**: `docs/LIMBOAI_INSTALLATION.md`

**What's included**:
- Asset Library installation (easiest)
- Manual installation from GitHub
- Headless server setup
- Verification tests
- Troubleshooting

**Start here** if you haven't installed LimboAI yet.

### 2. Refactoring Guide
**File**: `docs/LIMBOAI_REFACTOR_GUIDE.md`

**What's included**:
- High-level architecture decisions
- 6-phase implementation plan
- Before/after code comparisons
- Custom node specifications
- Network synchronization
- Debugging strategies

**Main reference** for the refactoring process.

### 3. BT Examples
**File**: `docs/LIMBOAI_BT_EXAMPLES.md`

**What's included**:
- Complete BT structures for all bot types
- Player controller BT
- Bomb lifecycle BT
- Advanced patterns (utility selectors, interrupts)
- Performance optimization
- Testing examples

**Use this** for concrete BT implementations.

## 🚀 Quick Start

### Step 1: Install LimboAI (10 minutes)

```bash
# Open project in Godot Editor
godot --path /path/to/Neptune-Bomberman

# In Godot Editor:
# 1. Click "AssetLib" tab
# 2. Search "LimboAI"
# 3. Click Download → Install
# 4. Project → Reload Project

# Verify installation
# Try creating a new node → Search "BTPlayer"
# If BTPlayer appears, you're good to go!
```

### Step 2: Test with Simple BT (30 minutes)

Create a test scene to verify LimboAI works:

```gdscript
# test_limboai_scene.gd
extends Node2D

func _ready():
    # Create a simple test
    var bt_player = BTPlayer.new()
    add_child(bt_player)
    
    # Load a test BehaviorTree
    var bt = BehaviorTree.new()
    bt_player.behavior_tree = bt
    
    # Setup blackboard
    bt_player.blackboard.set_var("test_value", 42)
    
    print("✅ LimboAI test successful!")
    print("   BTPlayer: ", bt_player)
    print("   BehaviorTree: ", bt)
```

### Step 3: Implement First Real BT (1-2 hours)

Start with the bomb lifecycle (simplest):

**File**: `res://shared/ai/limbo_trees/bomb_lifecycle.tres`

1. Create new BehaviorTree resource:
   - Right-click in FileSystem
   - New Resource → BehaviorTree
   - Save as `bomb_lifecycle.tres`

2. Open BT editor:
   - Double-click the resource
   - Bottom panel → LimboAI tab

3. Build tree:
   ```
   BTSequence (root)
   ├── BTCheckFuseExpired (custom condition)
   └── BTExplodeBomb (custom action)
   ```

4. Attach to ServerBomb:
   ```gdscript
   # In server_bomb.gd
   var bt_player: BTPlayer
   
   func _ready():
       bt_player = BTPlayer.new()
       add_child(bt_player)
       
       bt_player.behavior_tree = preload("res://shared/ai/limbo_trees/bomb_lifecycle.tres")
       bt_player.blackboard.set_var("bomb", self)
   ```

### Step 4: Refactor One Bot Personality (2-3 hours)

Pick the "Balanced" bot to start:

1. **Create BT Resource**: `res://shared/ai/limbo_trees/bot_balanced.tres`

2. **Build Tree Structure** (use examples from `LIMBOAI_BT_EXAMPLES.md`)

3. **Update bot_controller.gd**:
   ```gdscript
   # Replace custom BTRunner with BTPlayer
   var bt_player: BTPlayer
   
   func configure(...):
       bt_player = BTPlayer.new()
       add_child(bt_player)
       bt_player.behavior_tree = load("res://shared/ai/limbo_trees/bot_balanced.tres")
       _setup_blackboard()
   ```

4. **Test**: Spawn a bot and verify behavior matches original

### Step 5: Implement Player Input System (3-4 hours)

This is the most complex part:

1. **Add InputBuffer to ServerPlayer**:
   ```gdscript
   # In server_player.gd
   const InputBufferScript = preload("res://shared/entities/input_buffer.gd")
   var input_buffer: InputBuffer = InputBuffer.new()
   var bt_player: BTPlayer
   
   func _ready():
       # Existing setup...
       _setup_player_bt()
   
   func _setup_player_bt():
       bt_player = BTPlayer.new()
       add_child(bt_player)
       bt_player.behavior_tree = preload("res://shared/ai/limbo_trees/player_controller.tres")
       bt_player.blackboard.set_var("player", self)
       bt_player.blackboard.set_var("input_buffer", input_buffer)
   
   func queue_input(input_data: Dictionary):
       input_buffer.push_input(input_data)
   ```

2. **Create Player BT**: Use structure from `LIMBOAI_BT_EXAMPLES.md`

3. **Update game_instance.gd**:
   ```gdscript
   # Replace direct input processing with queueing
   func handle_player_input(peer_id: int, input_data: Dictionary):
       if not players.has(peer_id):
           return
       
       var player = players[peer_id]
       player.queue_input(input_data)  # BT will process it
   ```

4. **Test**: Connect client and verify all inputs work

### Step 6: Full Integration Testing (2-3 hours)

Test all scenarios:
- [ ] Single bot behaves correctly
- [ ] Multiple bots interact properly
- [ ] Player movement feels responsive
- [ ] Player bomb placement works
- [ ] Power Glove mechanics work
- [ ] Multiplayer (bot + human) works
- [ ] No new desyncs introduced
- [ ] Performance is acceptable

## 📁 File Structure

After refactoring, your project will have:

```
Neptune-Bomberman/
├── docs/
│   ├── LIMBOAI_INSTALLATION.md      # Start here
│   ├── LIMBOAI_REFACTOR_GUIDE.md    # Main guide
│   ├── LIMBOAI_BT_EXAMPLES.md       # Examples
│   └── LIMBOAI_QUICKSTART.md        # This file
│
├── server/
│   ├── ai/
│   │   ├── tasks/             # Custom BT nodes (res://ai/tasks)
│   │   │   ├── conditions/
│   │   │   │   ├── bt_is_in_danger.gd
│   │   │   │   ├── bt_is_cell_walkable.gd
│   │   │   │   ├── bt_has_powerup.gd
│   │   │   │   └── bt_has_client_input.gd
│   │   │   ├── actions/
│   │   │   │   ├── bt_move_to_cell.gd
│   │   │   │   ├── bt_place_bomb.gd
│   │   │   │   ├── bt_update_input_from_buffer.gd
│   │   │   │   ├── bt_process_power_glove.gd
│   │   │   │   └── bt_find_escape_route.gd
│   │   │   └── composites/
│   │   │       └── bt_utility_selector.gd
│   │   └── trees/
│   │       └── bot_default.tres
│   │
│   └── shared/
│       └── ...

> **Note:** The top-level project also exposes `res://ai/tasks` as a symlink to `server/ai/tasks` so the LimboAI editor can discover these tasks using the default search path.
│
├── server/
│   ├── ai/
│   │   ├── bot_controller.gd        # Modified to use LimboAI
│   │   └── bot_manager.gd           # Modified to use LimboAI
│   └── game_instance.gd             # Modified input handling
│
└── addons/
    └── limboai/                      # Installed from Asset Library
        ├── bin/
        ├── icons/
        ├── limboai.gdextension
        └── plugin.cfg
```

## 🛠️ Custom Nodes Reference

All custom nodes are in `server/ai/tasks/`:

### Conditions
- **BTIsInDanger**: Check if entity is in explosion danger
- **BTIsCellWalkable**: Check if a cell is traversable
- **BTHasPowerup**: Check if player has specific powerup
- **BTHasClientInput**: Check if client input is available

### Actions
- **BTMoveToCell**: Move entity toward target cell
- **BTPlaceBomb**: Place bomb at current position
- **BTUpdateInputFromBuffer**: Read client inputs
- **BTProcessPowerGlove**: Handle Power Glove logic
- **BTFindEscapeRoute**: Calculate escape path from danger

## 🐛 Common Issues

### Issue: "BTPlayer node not found"
**Solution**: Reload project after installing LimboAI

### Issue: "Blackboard variable not found"
**Solution**: Make sure to set all required blackboard variables in `_ready()` or `configure()`

### Issue: "Bot doesn't move"
**Solution**: 
1. Check that `target_cell` is set in blackboard
2. Verify `BTMoveToCell` is being executed (use debugger)
3. Ensure `player.set_input()` is being called

### Issue: "Player input feels laggy"
**Solution**:
1. Reduce input buffer size (currently 10)
2. Process inputs every frame (not every other frame)
3. Use `peek_only=true` in `BTUpdateInputFromBuffer`

### Issue: "Desyncs in multiplayer"
**Solution**:
1. Ensure BTs only run on server
2. Check that blackboard is updated before BT tick
3. Verify state sync is unchanged

## 📊 Performance Tips

1. **Vary Tick Rates**:
   ```gdscript
   # Tick distant bots less frequently
   if bot.distance_to_player > 500:
       if Engine.get_physics_frames() % 4 == 0:
           bot.bt_player.update(delta * 4)
   else:
       bot.bt_player.update(delta)
   ```

2. **Cache Expensive Conditions**:
   ```gdscript
   # In custom condition node
   var _cached_result: int
   var _cache_time: float
   
   func _tick(delta):
       if Time.get_ticks_msec() - _cache_time < 100:  # 100ms cache
           return _cached_result
       _cached_result = _expensive_calculation()
       _cache_time = Time.get_ticks_msec()
       return _cached_result
   ```

3. **Use Subtrees**: Share common behaviors between personalities

## 🧪 Testing

### Unit Test Example

```gdscript
# test_player_bt.gd
extends GutTest

func test_player_places_bomb():
    var game = autoqfree(GameInstance.new())
    add_child(game)
    
    var player_id = 1
    game.add_player(player_id, "TestPlayer")
    
    # Queue bomb placement input
    var player = game.players[player_id]
    player.queue_input({"place_bomb": true})
    
    # Let BT process
    await get_tree().physics_frame
    
    # Verify bomb was placed
    assert_eq(game.bombs.size(), 1, "Bomb should be placed")
```

### Integration Test

```gdscript
func test_bot_escapes_danger():
    var game = autoqfree(GameInstance.new())
    add_child(game)
    
    # Spawn bot
    game.spawn_bot("BALANCED")
    var bot = game.players.values()[0]
    var initial_pos = bot.position
    
    # Place bomb next to bot
    var bomb_pos = initial_pos + Vector2(64, 0)
    # ... create bomb at bomb_pos
    
    # Wait for bot to react
    await get_tree().create_timer(1.0).timeout
    
    # Verify bot moved away
    assert_gt(bot.position.distance_to(initial_pos), 32, "Bot should escape")
```

## 📖 Learning Resources

### Official LimboAI
- **Docs**: https://limboai.readthedocs.io/
- **GitHub**: https://github.com/limbonaut/limboai
- **Discord**: https://discord.gg/N5MGC95GpP

### Behavior Trees General
- **Introduction**: https://limboai.readthedocs.io/en/stable/behavior-trees/introduction.html
- **AI Programming Wisdom**: http://www.gameaipro.com/
- **GDC Talks**: Search "GDC Behavior Trees" on YouTube

## ✅ Checklist

Before considering the refactoring complete:

- [ ] LimboAI installed and verified
- [ ] All custom nodes created and tested
- [ ] Input buffer system implemented
- [ ] Bomb lifecycle using BT (optional but recommended)
- [ ] At least one bot personality refactored
- [ ] Player controller refactored
- [ ] All multiplayer scenarios tested
- [ ] No performance regressions
- [ ] No new desyncs
- [ ] Documentation updated
- [ ] Team trained on new system

## 🎉 Success Criteria

You'll know the refactoring is successful when:

1. ✅ All bots behave as before (or better)
2. ✅ Player controls feel identical
3. ✅ LimboAI debugger shows tree execution
4. ✅ Can modify bot behavior by editing BT (no code changes)
5. ✅ Performance is same or better
6. ✅ Team prefers the new system

## 💡 Tips for Success

1. **Start Small**: Do bomb lifecycle first, then one bot, then all bots, finally players
2. **Test Often**: After each change, verify behavior matches original
3. **Use Debugger**: LimboAI's visual debugger is your best friend
4. **Document Decisions**: Note why you structured trees a certain way
5. **Keep Original Code**: Comment out old code, don't delete (easy rollback)

## 🆘 Getting Help

If you get stuck:

1. **Check Documentation**: Re-read the guides
2. **LimboAI Examples**: Look at the demo project
3. **Discord**: LimboAI community is very helpful
4. **GitHub Issues**: Search for similar issues
5. **This PR**: Leave comments on specific files

## 🔄 Rollback Plan

If you need to revert:

1. The old custom BT system still exists in `shared/ai/behavior_tree/`
2. Simply stop using `BTPlayer` and go back to `BTRunner`
3. Remove the `input_buffer` from `ServerPlayer`
4. Restore original `handle_player_input()` logic

Nothing is lost - you can switch back anytime!

---

## 📞 Contact

For questions about this refactoring:
- **GitHub**: @elgansayer
- **Project**: Neptune-Bomberman

Good luck with the refactoring! 🚀
