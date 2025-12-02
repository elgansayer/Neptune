---
applyTo: '**/*.gd,**/*.tscn,**/*.tres'
---

# Godot Development: Prefer Nodes Over Code

## Core Principle
**ALWAYS prefer using Godot's built-in nodes and editor-editable resources over writing code.**

This makes the game easier to edit, tweak, and debug directly in the Godot editor without recompiling or modifying scripts.

---

## Animation

### ✅ DO: Use AnimationPlayer
- Create animations in the editor with keyframes
- Edit timing, easing, and values visually
- Preview animations in real-time

### ❌ DON'T: Use programmatic Tweens for complex animations
```gdscript
# AVOID THIS when possible:
var tween = create_tween()
tween.tween_property(sprite, "scale", Vector2(1.2, 1.2), 0.3)
tween.tween_property(sprite, "position:y", -10, 0.2)
```

### ⚠️ Exception: Dynamic values
Use tweens ONLY when animation values must be calculated at runtime (e.g., based on tile size):
```gdscript
# OK - values depend on runtime tile_size
tween.tween_property(sprite, "scale", Vector2(calculated_scale, calculated_scale), 0.3)
```

---

## Timers

### ✅ DO: Use Timer nodes
```
[node name="RespawnTimer" type="Timer" parent="."]
wait_time = 3.0
one_shot = true
[connection signal="timeout" from="RespawnTimer" to="." method="_on_respawn"]
```

### ❌ DON'T: Use await get_tree().create_timer()
```gdscript
# AVOID:
await get_tree().create_timer(3.0).timeout
_respawn()
```

---

## Audio

### ✅ DO: Use AudioStreamPlayer nodes in scene
- Assign audio streams in the editor
- Configure volume, bus, and properties visually

### ❌ DON'T: Create audio players in code
```gdscript
# AVOID:
var player = AudioStreamPlayer.new()
player.stream = preload("res://sound.ogg")
add_child(player)
```

---

## Particles

### ✅ DO: Use GPUParticles2D/CPUParticles2D nodes
- Design particle effects in editor
- Export parameters for runtime tweaking

### ❌ DON'T: Manually spawn sprites in loops

---

## UI Layout

### ✅ DO: Use Container nodes (VBox, HBox, Grid, Margin)
- Let Godot handle layout automatically
- Responsive to different screen sizes

### ❌ DON'T: Position UI elements with code
```gdscript
# AVOID:
label.position = Vector2(screen_width / 2 - label.size.x / 2, 100)
```

---

## State Machines

### ✅ DO: Use AnimationTree with StateMachine
- Visual state transitions
- Blend trees for smooth animations

### ❌ DON'T: Giant match statements
```gdscript
# AVOID large state machines in code when AnimationTree can handle it
match state:
    IDLE: ...
    WALK: ...
    RUN: ...
```

---

## Resources

### ✅ DO: Use .tres Resource files
- ItemData, EnemyStats, WeaponConfig as Resources
- Edit values in Inspector
- Swap configurations without code changes

### ❌ DON'T: Hardcode configuration in scripts
```gdscript
# AVOID:
const ENEMY_HEALTH = 100
const ENEMY_SPEED = 50
```

---

## Collision

### ✅ DO: Set collision layers/masks in editor
### ❌ DON'T: Set them in code unless dynamic

---

## Summary Checklist

Before writing code, ask:
1. Can I use a built-in node for this? (Timer, AnimationPlayer, Particles, etc.)
2. Can I expose this as an @export for editor tweaking?
3. Can I create a .tres Resource for this data?
4. Can this be done with signals and editor connections?

**If yes to any → use the node/editor approach first.**
