# Tirra Mount System Integration Guide

## Overview

This document provides instructions for integrating the **Tirra** mount system into the Bomberman game. A Tirra is a rideable creature (like a Rooey/Louie from Sega Saturn Bomberman) that the player can pick up as an item. When mounted, the Tirra takes over movement animations while the player displays a riding animation.

---

## What is a Tirra?

A **Tirra** is a mount creature with these characteristics:
- **Spawns from Eggs**: When a player walks over an egg item, a Tirra hatches
- **Mountable**: Player automatically jumps onto the Tirra when walking over it
- **Takes Over Movement**: While riding, the Tirra animates for walk/stopped, player stays in `ride` animation
- **Special Actions**: The action button triggers Tirra-specific abilities (kick, dash, jump, etc.)
- **Growth Stages**: Tirras have 3 growth levels - BABY, TEEN, ADULT - each with different offsets and potentially different abilities
- **Takes the Hit**: When hit by an explosion, the Tirra dies instead of the player (player dismounts safely)

---

## Reference Files

### Tirra Controller API
**Location**: `pack projects/tirra/blue/controller.gd`

The controller is attached to the root of the Tirra scene and provides:

```gdscript
# Signals
signal action_started(action_name, action_type)  # Emitted when action begins
signal action_stopped(action_name, action_type)  # Emitted when action animation finishes
signal action_info(info_dict)                    # Emitted on frame changes with offset data

# Enums
enum GrowthLevel { BABY, TEEN, ADULT }

# Properties
@export var current_level: GrowthLevel = GrowthLevel.BABY
@export var offset_baby: Vector2 = Vector2(0, -10)
@export var offset_teen: Vector2 = Vector2(0, -20)
@export var offset_adult: Vector2 = Vector2(0, -30)
@export var frame_offsets: Dictionary = {}  # Per-frame fine-tuning

# Methods
func set_growth_level(level: GrowthLevel) -> void
func get_rider_offset() -> Vector2         # Base offset for current growth level
func get_dynamic_offset() -> Vector2       # Offset including per-frame adjustments
func run_action(action_name: String) -> Dictionary  # Returns action info
```

### Tirra Scene Structure
**Location**: `pack projects/tirra/blue/tirra.tscn`

```
tirra (Node2D with controller.gd)
├── baby (AnimatedSprite2D) - visible when current_level == BABY
├── teen (AnimatedSprite2D) - visible when current_level == TEEN
└── adult (AnimatedSprite2D) - visible when current_level == ADULT
```

### Available Animations per Growth Level
Each AnimatedSprite2D has these animations:
- `idle` - Idle looking around
- `down_stopped`, `up_stopped`, `left_stopped`, `right_stopped` - Directional stopped
- `down_walk`, `up_walk`, `left_walk`, `right_walk` - Directional walking
- `down_kick`, `up_kick`, `left_kick`, `right_kick` - Directional action (kick)
- `killed` - Death animation
- `win` - Victory celebration

---

## Integration Steps

### Step 1: PCK Loading

Mount the Tirra PCK file at game startup. Add to your PCK loader autoload:

```gdscript
# In scripts/pck_loader.gd or equivalent
func _ready():
    # Existing player PCK
    ProjectSettings.load_resource_pack("res://characters/player-robin-hood.pck")
    
    # Tirra PCK (blue variant for now)
    var tirra_pck = "res://characters/blue-tirra.pck"
    if FileAccess.file_exists(tirra_pck):
        ProjectSettings.load_resource_pack(tirra_pck)
        print("[PCKLoader] Tirra PCK mounted: ", tirra_pck)
```

### Step 2: Create Tirra Item (Egg Spawner)

The existing `items/egg.gd` already has placeholder logic. Update it to properly spawn Tirras:

```gdscript
# items/egg.gd
extends "res://items/item.gd"

## Egg power-up - spawns a Tirra mount

func award_player(player) -> void:
    print("[Egg] Hatching Tirra for player")
    
    # Spawn Tirra at egg position
    var tirra_scene = load("res://tirra.tscn")  # From PCK
    if not tirra_scene:
        push_warning("[Egg] Failed to load tirra.tscn from PCK")
        return
    
    var tirra = tirra_scene.instantiate()
    tirra.position = global_position
    tirra.add_to_group("tirras")
    tirra.add_to_group("pickups")  # So player can pick it up
    
    get_parent().add_child(tirra)
```

### Step 3: Player Tirra Mounting System

Add these properties and methods to your player script:

```gdscript
# In shared/entities/server_player.gd or equivalent

# Tirra mount state
var mounted_tirra: Node2D = null  # Reference to current Tirra
var is_mounted: bool = false

# Signals for client sync
signal tirra_mounted(tirra_node)
signal tirra_dismounted()
signal tirra_action_triggered(action_name, action_type)

func mount_tirra(tirra: Node2D) -> bool:
    """Mount a Tirra. Called when player walks over a Tirra item."""
    if is_mounted:
        return false  # Already riding
    
    mounted_tirra = tirra
    is_mounted = true
    
    # Reparent Tirra to player (or just track reference)
    tirra.get_parent().remove_child(tirra)
    add_child(tirra)
    tirra.position = Vector2.ZERO  # Local to player
    
    # Connect Tirra signals
    if tirra.has_signal("action_started"):
        tirra.action_started.connect(_on_tirra_action_started)
    if tirra.has_signal("action_stopped"):
        tirra.action_stopped.connect(_on_tirra_action_stopped)
    if tirra.has_signal("action_info"):
        tirra.action_info.connect(_on_tirra_action_info)
    
    tirra_mounted.emit(tirra)
    return true

func dismount_tirra(kill_tirra: bool = false) -> void:
    """Dismount from current Tirra."""
    if not is_mounted or not mounted_tirra:
        return
    
    # Disconnect signals
    if mounted_tirra.has_signal("action_started"):
        mounted_tirra.action_started.disconnect(_on_tirra_action_started)
    if mounted_tirra.has_signal("action_stopped"):
        mounted_tirra.action_stopped.disconnect(_on_tirra_action_stopped)
    if mounted_tirra.has_signal("action_info"):
        mounted_tirra.action_info.disconnect(_on_tirra_action_info)
    
    if kill_tirra:
        # Play death animation then free
        mounted_tirra.run_action("killed") if mounted_tirra.has_method("run_action") else null
        mounted_tirra.queue_free()
    else:
        # Return Tirra to world as pickup again
        var world_pos = global_position
        remove_child(mounted_tirra)
        get_parent().add_child(mounted_tirra)
        mounted_tirra.global_position = world_pos
    
    mounted_tirra = null
    is_mounted = false
    tirra_dismounted.emit()

func get_rider_offset() -> Vector2:
    """Get current rider offset from Tirra controller."""
    if not is_mounted or not mounted_tirra:
        return Vector2.ZERO
    
    if mounted_tirra.has_method("get_dynamic_offset"):
        return mounted_tirra.get_dynamic_offset()
    elif mounted_tirra.has_method("get_rider_offset"):
        return mounted_tirra.get_rider_offset()
    
    return Vector2.ZERO

func trigger_tirra_action() -> void:
    """Called when player presses action button while mounted."""
    if not is_mounted or not mounted_tirra:
        return
    
    if mounted_tirra.has_method("run_action"):
        var info = mounted_tirra.run_action("kick")  # Default action
        if info.get("started", false):
            tirra_action_triggered.emit(info["action"], info.get("type", "physical"))

func _on_tirra_action_started(action_name: String, action_type: String) -> void:
    # Handle action effects based on type
    match action_type:
        "physical":
            _handle_physical_action(action_name)
        "speed":
            _handle_speed_action(action_name)
        "defensive":
            _handle_defensive_action(action_name)

func _on_tirra_action_stopped(action_name: String, action_type: String) -> void:
    # Return to normal state after action
    pass

func _on_tirra_action_info(info: Dictionary) -> void:
    # Update rider position with frame offset
    pass

func _handle_physical_action(action_name: String) -> void:
    """Handle physical actions like kick."""
    match action_name:
        "kick":
            # Kick bombs in facing direction
            _kick_nearby_bomb()

func _handle_speed_action(action_name: String) -> void:
    """Handle speed-based actions like dash."""
    match action_name:
        "dash":
            # Temporary speed boost
            pass

func _handle_defensive_action(action_name: String) -> void:
    """Handle defensive actions like jump."""
    match action_name:
        "jump":
            # Jump over obstacles/bombs
            pass
```

### Step 4: Tirra Pickup Detection

Add collision detection for picking up Tirras:

```gdscript
# In server_player.gd collision handling

func _on_body_entered(body: Node) -> void:
    # ... existing powerup code ...
    
    # Check for Tirra pickup
    if body.is_in_group("tirras") and not is_mounted:
        mount_tirra(body)
```

### Step 5: Animation Delegation

Update the client animation system to delegate to Tirra when mounted:

```gdscript
# In client/game_view.gd update_player() function

func update_player_animation(player_node: Node2D, player_data: Dictionary) -> void:
    var anim_sprite = player_node.get_meta("animated_sprite")
    if not anim_sprite:
        return
    
    var is_mounted = player_data.get("is_mounted", false)
    var velocity = player_data.get("velocity", 0.0)
    var facing = player_data.get("facing", "DOWN")
    
    # Direction mapping
    var direction = _facing_to_direction(facing)  # Returns "south", "north", etc.
    
    if is_mounted:
        # Player shows ride animation
        var ride_anim = direction + "_ride"
        if anim_sprite.sprite_frames.has_animation(ride_anim):
            if anim_sprite.animation != ride_anim:
                anim_sprite.play(ride_anim)
        
        # Tirra handles movement animation
        var tirra = player_node.get_node_or_null("tirra")
        if tirra:
            _animate_tirra(tirra, velocity, facing)
            
            # Position player on Tirra with offset
            var rider_offset = tirra.get_dynamic_offset() if tirra.has_method("get_dynamic_offset") else Vector2(0, -10)
            anim_sprite.position = rider_offset
    else:
        # Normal player animation (existing code)
        anim_sprite.position = Vector2.ZERO
        if velocity > 10.0:
            _play_walk_animation(anim_sprite, direction)
        else:
            _play_stopped_animation(anim_sprite, direction)

func _animate_tirra(tirra: Node2D, velocity: float, facing: String) -> void:
    """Animate the Tirra based on movement."""
    var tirra_sprite = tirra.get_node_or_null("baby")  # or current growth level
    if not tirra_sprite:
        return
    
    # Map facing to tirra direction format
    var tirra_dir = "down"
    match facing:
        "UP": tirra_dir = "up"
        "DOWN": tirra_dir = "down"
        "LEFT": tirra_dir = "left"
        "RIGHT": tirra_dir = "right"
    
    var anim_name = ""
    if velocity > 10.0:
        anim_name = tirra_dir + "_walk"
    else:
        anim_name = tirra_dir + "_stopped"
    
    if tirra_sprite.sprite_frames.has_animation(anim_name):
        if tirra_sprite.animation != anim_name:
            tirra_sprite.play(anim_name)
```

### Step 6: Action Button Handling

Wire up the action input to trigger Tirra actions:

```gdscript
# In player input handling

func _process_input() -> void:
    # ... existing movement input ...
    
    # Action button (bomb place / tirra action)
    if Input.is_action_just_pressed("action"):
        if is_mounted:
            trigger_tirra_action()
        else:
            place_bomb()
```

### Step 7: Explosion Hit Handling

When a mounted player is hit, the Tirra dies instead:

```gdscript
# In explosion damage handling

func take_explosion_hit() -> void:
    if is_mounted:
        # Tirra takes the hit, player survives
        dismount_tirra(true)  # kill_tirra = true
        # Optional: brief invincibility for player
        start_invincibility_frames(1.0)
    else:
        # Normal player death
        die()
```

---

## Network Synchronization

For multiplayer, add these fields to the player state sync:

```gdscript
# State to send to clients
func get_network_state() -> Dictionary:
    var state = {
        # ... existing state ...
        "is_mounted": is_mounted,
        "tirra_level": mounted_tirra.current_level if mounted_tirra else 0,
        "tirra_animation": get_tirra_animation() if is_mounted else "",
    }
    return state
```

---

## Tirra Action Types

The controller's `run_action()` returns an info dictionary with a `type` field. Use this to determine player behavior:

| Type | Description | Example Actions |
|------|-------------|-----------------|
| `physical` | Direct physical attack/interaction | `kick` - Kicks bombs in facing direction |
| `speed` | Movement-based ability | `dash` - Quick burst of speed |
| `defensive` | Protective ability | `jump` - Jump over obstacles/bombs |
| `special` | Unique ability | `fire_breath` - Shoot flames |

---

## Testing Checklist

1. **PCK Loading**
   - [ ] `blue-tirra.pck` mounts successfully at startup
   - [ ] `res://tirra.tscn` loads from PCK

2. **Spawning**
   - [ ] Egg item hatches Tirra on pickup
   - [ ] Tirra appears at correct position
   - [ ] Tirra is in `tirras` and `pickups` groups

3. **Mounting**
   - [ ] Player auto-mounts when walking over Tirra
   - [ ] Player animation switches to `{direction}_ride`
   - [ ] Tirra becomes child of player
   - [ ] Player position offset applied correctly

4. **Movement While Mounted**
   - [ ] Tirra plays `{direction}_walk` when moving
   - [ ] Tirra plays `{direction}_stopped` when idle
   - [ ] Player stays in `ride` animation during movement
   - [ ] Dynamic offset adjusts per-frame

5. **Actions**
   - [ ] Action button triggers Tirra action
   - [ ] Tirra plays `{direction}_kick` animation
   - [ ] Action effect (kick bomb) works correctly
   - [ ] Action signals fire correctly

6. **Explosion Handling**
   - [ ] Tirra dies on explosion hit
   - [ ] Player dismounts safely
   - [ ] `killed` animation plays on Tirra
   - [ ] Player gains brief invincibility

7. **Network Sync**
   - [ ] Mounted state syncs to other clients
   - [ ] Tirra animations visible to all players
   - [ ] Rider offset correct on remote clients

---

## Example: Complete Tirra Pickup Flow

```
1. Player walks over Egg item
2. Egg plays pickup animation + sound
3. Egg spawns Tirra at same position
4. Egg deletes itself

5. Player walks over spawned Tirra
6. Tirra collision triggers mount_tirra()
7. Tirra becomes child of player at local origin
8. Player animation -> {direction}_ride
9. Tirra animation -> {direction}_stopped

10. Player presses movement input
11. Player position updates (server authority)
12. Tirra animation -> {direction}_walk
13. Player stays in {direction}_ride
14. Player sprite offset = tirra.get_dynamic_offset()

15. Player stops moving
16. Tirra animation -> {direction}_stopped
17. Player stays in {direction}_ride

18. Player presses action button
19. trigger_tirra_action() called
20. tirra.run_action("kick") executed
21. Tirra animation -> {direction}_kick
22. Kick detection runs (bombs in front)
23. action_stopped signal fires
24. Tirra returns to stopped/walk state

25. Explosion hits player
26. dismount_tirra(true) called
27. Tirra plays "killed" animation
28. Tirra queue_free() after animation
29. Player gains invincibility frames
30. Player animation -> normal (no ride)
```

---

## Future Enhancements

1. **Multiple Tirra Colors**: Load different `{color}-tirra.pck` files with unique abilities
2. **Growth System**: Collect more eggs to level up (Level 1 → Level 2 → Level 3)
3. **Tirra Abilities by Color** (see Saturn Bomberman reference below)
4. **Tirra Victory Animations**: Play `win` animation on round victory
5. **Tirra Health**: Some Tirras could survive multiple hits

---

## Saturn Bomberman Tirra Abilities Reference

The Tirras (dinosaur mounts) grant the rider a special ability and an extra hit point. Their abilities grow stronger at **Level 2** and **Level 3** (achieved by collecting more Egg items).

### 💙 Blue Tirra: High Kick (Bomb Launch) - **IMPLEMENTED**

Launches bombs over obstacles - they fly through the air and land at the target tile.

| Level | Range | Description |
|-------|-------|-------------|
| Level 1 (BABY) | 2 tiles | Kick bomb over obstacles, lands 2 tiles away |
| Level 2 (TEEN) | 4 tiles | Extended range, clears wider gaps |
| Level 3 (ADULT) | 6 tiles | Maximum range for long-distance targeting |

**Key Feature**: The bomb passes OVER all obstacles (soft blocks, hard blocks, walls, players). Bomb fuse resets on landing.

### 💜 Purple Tirra: Sonic Wave (Screech) - *Not Implemented*

Detonates bombs and reveals hidden items.

| Level | Range | Effect |
|-------|-------|--------|
| Level 1 | 3 tiles | Detonates bombs, reveals hidden items |
| Level 2 | 4 tiles | Extended range |
| Level 3 | 7 tiles | Massive area effect |

### 💚 Green Tirra: Dash - *Not Implemented*

High-speed straight-line movement.

| Level | Speed/Control | Effect |
|-------|---------------|--------|
| Level 1 | Slow | Dash until hitting obstacle, brief stun after |
| Level 2 | Fast + Stop | Can stop mid-dash |
| Level 3 | Faster + Turn | Can change direction mid-dash |

### 💛 Yellow Tirra: Roar (Stun) - *Not Implemented*

Stuns opponents and causes power-up drops.

| Level | Range | Effect |
|-------|-------|--------|
| Level 1 | 3 tiles | Stuns enemies 1-2 seconds |
| Level 2 | 6 tiles | Extended range |
| Level 3 | 9 tiles | Massive area stun |

### 💖 Pink Tirra: Jump - *Not Implemented*

Vertical movement to bypass obstacles.

| Level | Distance | Can Jump Over |
|-------|----------|---------------|
| Level 1 | 2 tiles | Bombs, enemies, soft blocks |
| Level 2 | 4 tiles | + Hard blocks |
| Level 3 | 6 tiles | Maximum distance |

---

## Reference: Saturn Bomberman Tirra Behavior

In Sega Saturn Bomberman (called "Rooeys" or "Louies"):
- Eggs spawn randomly in destructible blocks
- Walking over an egg hatches the creature
- Walking over the creature mounts it
- B button triggers the creature's special ability
- Getting hit dismounts (creature dies, player survives one hit)
- Different colors have different abilities:
  - Green: Dash through soft blocks
  - Blue: Kick bombs (HIGH KICK - over obstacles)
  - Pink: Jump over bombs/blocks
  - Yellow: Roar (stun opponents)
  - Purple: Sonic wave (detonate bombs, reveal items)

This implementation follows the same pattern while using the Tirra naming and visual style.
