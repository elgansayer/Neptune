# Godot-Native Rendering System

## Overview
This project uses **Godot's built-in features** for optimal rendering performance and maintainability:

1. **Y-Sorting** - Automatic depth perception based on Y position
2. **CanvasLayers** - Major separation (Background, Game, UI, Debug)
3. **Z-Index** - Fine-grained layering within the same CanvasLayer
4. **Node Groups** - Batch updates to rendering layers

## Architecture

### CanvasLayers (Major Separation)
```
CANVAS_BACKGROUND (-10): Tiles, floor, shadows
CANVAS_GAME (0):         Main gameplay with Y-sorting enabled
CANVAS_UI (10):          HUD, menus (no Y-sorting)
CANVAS_DEBUG (100):      Debug overlays, visualizers
```

**Why CanvasLayers?**
- Complete rendering isolation
- Independent camera following
- GPU-optimized layer compositing
- No z_index conflicts between layers

### Y-Sorting (Depth Perception)
Enabled on these containers:
- `game_view` (root)
- `players_container`
- `bombs_container`
- `explosions_container`

**How Y-Sorting Works:**
- Entities with **lower Y** render **behind** entities with higher Y
- Creates automatic depth illusion
- Works **within the same z_index**
- Zero performance cost (built-in Godot feature)

### Z-Index Layers (Within Game Canvas)
```gdscript
FLOOR:          -100  # Background tiles
SHADOWS:         -50  # Drop shadows
ITEMS:           -10  # Powerups, eggs
BOMBS:             0  # Default layer
EXPLOSIONS:       10  # Above bombs
PLAYER_BASE:     100  # Player sprite
PLAYER_EFFECTS:  150  # Mounted creatures
PLAYER_UI:       200  # Name tags, health bars
```

### Debug Layers (Within Debug Canvas)
```gdscript
DEBUG_PATHS:    1000  # AI pathfinding
DEBUG_ARROWS:   1001  # Direction indicators  
DEBUG_OVERLAY:  4096  # Safety/threat visualizers
```

## Implementation

### RenderingLayers Class
Central constants and utilities in `shared/rendering_layers.gd`:

```gdscript
const RenderingLayers = preload("res://shared/rendering_layers.gd")

# Setup node with z_index and optional group
RenderingLayers.setup_node(node, RenderingLayers.ITEMS, "render_items")

# Enable Y-sorting on container
RenderingLayers.setup_ysort_container(container)

# Create CanvasLayer
var canvas = RenderingLayers.create_canvas_layer(
    RenderingLayers.CANVAS_DEBUG,
    "DebugCanvas"
)
```

### Applied Rendering Layers

#### Items (Powerups, Eggs)
**File:** `client/ui/powerup_renderer.gd`, `client/game_view.gd`
```gdscript
z_index = RenderingLayers.ITEMS  # -10
```
- Renders below players
- Y-sorted for depth
- Visible behind player sprites

#### Bombs
**File:** `client/game_view.gd`
```gdscript
bomb_node.z_index = RenderingLayers.BOMBS  # 0
```
- Default layer (0)
- Y-sorted with explosions
- Below player layer

#### Explosions
**File:** `client/game_view.gd`
```gdscript
explosion_node.z_index = RenderingLayers.EXPLOSIONS  # 10
```
- Above bombs
- Below players
- Y-sorted for overlapping flames

#### Players
**File:** `client/ui/ClientPlayer.tscn`
```gdscript
[node name="ClientPlayer" type="Node2D"]
z_index = 100  # PLAYER_BASE

[node name="DebugArrow" type="Polygon2D" parent="."]
z_index = 1000  # DEBUG_PATHS (relative to parent)
z_as_relative = true
```
- Base layer: 100
- Debug overlays: 1000+ (relative)
- Always on top of gameplay elements

#### Debug Visualizers
**Files:** `client/ui/threat_matrix_visualizer.gd`, `client/ui/bomb_safety_visualizer.gd`
```gdscript
z_index = RenderingLayers.DEBUG_PATHS       # 1000
z_index = RenderingLayers.DEBUG_OVERLAY     # 4096
```
- Rendered on Debug CanvasLayer (100)
- Always on top of game canvas
- Toggle with F3/F4 keys

## Godot Features Used

### 1. CanvasLayer
**Godot Feature:** Separate rendering layers independent of scene tree
- Used for: Background, Game, UI, Debug separation
- Benefits: No z_index conflicts, independent transforms
- Documentation: https://docs.godotengine.org/en/stable/classes/class_canvaslayer.html

### 2. y_sort_enabled
**Godot Feature:** Automatic depth sorting based on Y position
- Used on: game_view, player/bomb/explosion containers
- Benefits: Free depth perception, no manual sorting
- Documentation: https://docs.godotengine.org/en/stable/classes/class_node2d.html#class-node2d-property-y-sort-enabled

### 3. z_index
**Godot Feature:** Manual layer ordering within same canvas
- Used for: Items, bombs, explosions, players
- Benefits: Precise control when Y-sorting isn't enough
- Documentation: https://docs.godotengine.org/en/stable/classes/class_node2d.html#class-node2d-property-z-index

### 4. z_as_relative
**Godot Feature:** Make z_index relative to parent
- Used on: Player debug overlays
- Benefits: Child nodes stack relative to parent z_index
- Documentation: https://docs.godotengine.org/en/stable/classes/class_node2d.html#class-node2d-property-z-as-relative

### 5. Node Groups
**Godot Feature:** Tag nodes for batch operations
- Used for: Rendering layer management
- Benefits: Update all items/bombs/explosions at once
- Documentation: https://docs.godotengine.org/en/stable/classes/class_scenetree.html#class-scenetree-method-get-nodes-in-group

## Visual Stacking Order (Bottom to Top)

```
┌─────────────────────────────────────┐
│  Debug Canvas (CanvasLayer 100)    │
│  ├─ Threat Matrix (z=1000)          │ ← F3 to toggle
│  └─ Bomb Safety (z=4096)            │ ← F4 to toggle
├─────────────────────────────────────┤
│  Game Canvas (CanvasLayer 0)        │ ← Y-Sorting enabled
│  ├─ Floor tiles (z=-100)            │
│  ├─ Shadows (z=-50)                 │
│  ├─ Items/Eggs (z=-10)              │ ← Y-sorted
│  ├─ Bombs (z=0)                     │ ← Y-sorted
│  ├─ Explosions (z=10)               │ ← Y-sorted
│  ├─ Players (z=100)                 │ ← Y-sorted
│  │   ├─ Sprite (relative z=0)       │
│  │   ├─ Effects (relative z=50)     │
│  │   └─ Debug (relative z=1000)     │
│  └─ Player UI (z=200)               │
├─────────────────────────────────────┤
│  Background Canvas (CanvasLayer -10)│
│  └─ Map background                  │
└─────────────────────────────────────┘
```

## Performance Benefits

### Y-Sorting
- **Cost:** Free (built-in Godot feature)
- **Benefit:** Automatic depth without manual sorting
- **Optimization:** Only enabled on containers that need it

### CanvasLayers
- **Cost:** Minimal (GPU-optimized compositing)
- **Benefit:** Complete isolation, no z_index conflicts
- **Optimization:** Only 3 layers (Background, Game, Debug)

### Z-Index
- **Cost:** Minimal (integer comparison)
- **Benefit:** Precise control within layers
- **Optimization:** Centralized constants, no magic numbers

### Node Groups
- **Cost:** Minimal (hash table lookup)
- **Benefit:** Batch updates to rendering properties
- **Optimization:** Only used when needed (debugging, effects)

## Testing

### Visual Verification
1. **Items below players:** ✅ Eggs/powerups render behind player sprites
2. **Y-sorting works:** ✅ Players at higher Y appear in front of lower Y players
3. **Explosions layer correctly:** ✅ Flames render above bombs, below players
4. **Debug overlays on top:** ✅ F3/F4 visualizers always visible

### Console Verification
Look for initialization messages:
```
[GameView] CanvasLayers configured: Game=0 Debug=100
[RenderingLayers] z=-10 group=render_items node=Powerup_123
[ThreatMatrixVisualizer] Initialized at position: (0, 0)
```

## Maintenance

### Adding New Entity Types
1. Choose appropriate z_index constant from `RenderingLayers`
2. Apply using `RenderingLayers.setup_node(node, layer, group)`
3. Document in this file

### Changing Layer Values
1. Update constants in `shared/rendering_layers.gd`
2. All entities update automatically (centralized)
3. Test visual stacking order

### Debugging Rendering Issues
1. Enable debug visualizers (F3/F4)
2. Check console for z_index assignments
3. Verify Y-sorting enabled on containers
4. Confirm CanvasLayer separation working

## References

- **Godot Y-Sorting:** https://docs.godotengine.org/en/stable/tutorials/2d/2d_sprite_animation.html#y-sorting
- **CanvasLayer:** https://docs.godotengine.org/en/stable/classes/class_canvaslayer.html
- **Z-Index:** https://docs.godotengine.org/en/stable/tutorials/2d/canvas_layers.html
- **Node2D:** https://docs.godotengine.org/en/stable/classes/class_node2d.html
