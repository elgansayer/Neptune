# Quick Start: Robin Hood Player

## Test the Player
```bash
# Quick test (opens window for 10 seconds)
./test-player.py

# Or manually:
godot --path . res://scenes/PlayerTest.tscn
```

## Controls
- **Arrow Keys** or **WASD**: Move player
- **Up/W**: Walk north (north_walk animation)
- **Down/S**: Walk south (south_walk animation)  
- **Left/A**: Walk west (west_walk animation)
- **Right/D**: Walk east (east_walk animation)
- **No input**: Idle (state_idle animation)

## Integration Checklist

✅ PCK file mounted at startup
✅ Player scene loads from `res://player.tscn`
✅ CharacterBody2D physics ready
✅ 4-directional movement implemented
✅ Animation system connected
✅ 30 animations available

## Use in Your Scene

```gdscript
# Method 1: Scene instance
var player = preload("res://characters/PlayerRobinHood.tscn").instantiate()
add_child(player)
player.position = Vector2(576, 324)

# Method 2: Direct code
var player = CharacterBody2D.new()
var script = load("res://characters/PlayerRobinHood.gd")
player.set_script(script)
add_child(player)
```

## Customization

### Change Speed
Edit `characters/PlayerRobinHood.gd`:
```gdscript
const SPEED = 300.0  # Change this value
```

### Add Collision
Add a CollisionShape2D as child of PlayerRobinHood in the scene editor

### Additional Animations
The PCK includes 30 total animations. To use others:
```gdscript
animated_sprite.play("east_jump")  # Jumping
animated_sprite.play("north_carry")  # Carrying items
animated_sprite.play("west_ride")  # Riding
# etc.
```

View all animations:
```bash
strings characters/player-robin-hood.pck | grep -E "^(north|south|east|west|state)_"
```

## Troubleshooting

**Player doesn't appear:**
- Check console for "[Player] Successfully loaded" message
- Verify PCK file exists at `characters/player-robin-hood.pck`

**No movement:**
- Check input map has ui_up, ui_down, ui_left, ui_right defined
- Verify player is CharacterBody2D with physics enabled

**No animations:**
- Check for "[Player] AnimatedSprite2D not found" error
- PCK may not have mounted correctly

## Files Reference

| File | Purpose |
|------|---------|
| `characters/player-robin-hood.pck` | Asset pack (86 KB) |
| `characters/PlayerRobinHood.tscn` | Player scene |
| `characters/PlayerRobinHood.gd` | Movement controller |
| `scripts/pck_loader.gd` | Auto-loads PCK |
| `scenes/PlayerTest.tscn` | Test environment |

## Next Steps

1. Add collision shape for gameplay
2. Integrate with existing game systems
3. Add bomb placement functionality
4. Connect to network player system
5. Remove old Player.tscn and Player2.tscn files
