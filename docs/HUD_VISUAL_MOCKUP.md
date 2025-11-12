# Visual Mockup: Simplified HUD for 9/10-Player Widescreen Battle Mode

## Full Screen Layout

```
╔════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                                ║
║   ◆◆◆ ◆◆◆             ╔════════════════════╗                    ◆◆◆ ◆◆                       ║
║   P1   P2             ║      3:00          ║                    P6   P7                       ║
║                       ╚════════════════════╝                                                  ║
║                              Timer Panel                                                      ║
╚════════════════════════════════════════════════════════════════════════════════════════════════╝

┌──────────┐                                                                    ┌──────────┐
│          │                                                                    │          │
│  Player1 │                                                                    │  Player6 │
│  ████    │                                                                    │  ████    │
│  Name    │                                                                    │  Name    │
│          │                                                                    │          │
├──────────┤                                                                    ├──────────┤
│          │                                                                    │          │
│  Player2 │                     [GAME ARENA]                                  │  Player7 │
│  ████    │                                                                    │  ████    │
│  Name    │                  Large widescreen                                 │  Name    │
│          │                    playing field                                  │          │
├──────────┤                                                                    ├──────────┤
│          │                 (15x11 or 17x13 tiles)                            │          │
│  Player3 │                                                                    │  Player8 │
│  ████    │                    Players move here                              │  ████    │
│  Name    │                    Bombs explode here                             │  Name    │
│          │                    Power-ups spawn here                           │          │
├──────────┤                                                                    ├──────────┤
│          │                                                                    │          │
│  Player4 │                                                                    │  Player9 │
│  ████    │                                                                    │  ████    │
│  Name    │                                                                    │  Name    │
│          │                                                                    │          │
├──────────┤                                                                    ├──────────┤
│          │                                                                    │          │
│  Player5 │                                                                    │  Player10│
│  ████    │                                                                    │  ████    │
│  Name    │                                                                    │  Name    │
│          │                                                                    │          │
└──────────┘                                                                    └──────────┘

Left Player                                                                    Right Player
Identifiers                                                                    Identifiers
```

## Component Details

### Top Bar (70px height)
```
╔════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                                ║
║   ◆ ◆ ◆ ◆              ╔════════════════════╗                    ◆ ◆ ◆ ◆ ◆ ◆                 ║
║   White Red            ║      2:47          ║                    Blue Yellow Green             ║
║   Black Blue           ╚════════════════════╝                    Pink Purple Orange            ║
║                                                                                                ║
╚════════════════════════════════════════════════════════════════════════════════════════════════╝
     ↑                                ↑                                      ↑
Left Score Tally              Timer Panel                           Right Score Tally
(Rounds won by P1-P4)       (White text on                        (Rounds won by P5-P10)
                             dark panel)
```

### Player Portrait (60x70px each)
```
┌──────────┐
│ ▓▓▓▓▓▓▓▓ │  ← 2px colored border (player color)
│ ▓        │
│ ▓  ████  │  ← 40x40px colored square (player color)
│ ▓  ████  │
│ ▓  ████  │
│ ▓        │
│ ▓ Player │  ← Player name, 10px font
│ ▓▓▓▓▓▓▓▓ │
└──────────┘
   ↑
Dark grey background
rgba(38,38,51,0.9)
```

### Diamond Score Icon (16x16px)
```
     ◆
    ╱ ╲
   ╱   ╲
  ╱     ╲
 ╱       ╲
╱         ╲
╲         ╱
 ╲       ╱
  ╲     ╱
   ╲   ╱
    ╲ ╱
     ◆
```
Created using Polygon2D with 4 points:
- Top: (8, 2)
- Right: (14, 8)
- Bottom: (8, 14)
- Left: (2, 8)

### Timer States
```
Normal (>60s):    ╔════════════╗
                  ║   3:00     ║  ← White text
                  ╚════════════╝

Warning (60-30s): ╔════════════╗
                  ║   0:45     ║  ← Yellow text
                  ╚════════════╝

Critical (<30s):  ╔════════════╗
                  ║   0:15     ║  ← Red text
                  ╚════════════╝
```

## Color Examples

### Player Colors in Action
```
Player 1 (White):      ┌─WHITE─────┐    Score: ◆ (white)
                       │  ████     │
                       │  Name     │
                       └───────────┘

Player 2 (Black):      ┌─BLACK─────┐    Score: ◆ (dark grey)
                       │  ████     │
                       │  Name     │
                       └───────────┘

Player 3 (Red):        ┌──RED──────┐    Score: ◆ (red)
                       │  ████     │
                       │  Name     │
                       └───────────┘

Player 4 (Blue):       ┌──BLUE─────┐    Score: ◆ (blue)
                       │  ████     │
                       │  Name     │
                       └───────────┘

... (up to 10 players)
```

## Implementation Notes

1. **Z-Layering**:
   - CanvasLayer at level 100 (always on top)
   - HUD elements never obscured by game objects

2. **Responsive Layout**:
   - Top bar: Anchored to top, spans full width
   - Player panels: Anchored to left/right edges, centered vertically
   - All elements use layout_mode for proper scaling

3. **Performance**:
   - Static layout, minimal updates
   - Only timer updates every frame
   - Player portraits and scores update on state changes only

4. **Visibility**:
   - All text has black shadows (2px offset, 80% opacity)
   - High contrast colors (bright on dark)
   - No semi-transparent elements that could obscure gameplay

## Comparison: Before vs After

### Before (Standard HUD):
```
╔════════════════════════════════════════════╗
║  3:00                    4 / 8 Players     ║
╚════════════════════════════════════════════╝

                [GAME ARENA]

┌─────────────────────┐
│ Player_1234         │
│ 💣 3 / 5            │
│ 🔥 Range: 4         │
│ ⚡ Speed: 120%      │
└─────────────────────┘
         ↑
    Bottom-left
    stats panel
```

### After (Simplified HUD):
```
╔════════════════════════════════════════════╗
║  ◆◆◆    ╔═══════╗     ◆◆◆                 ║
║          ║ 3:00  ║                         ║
║          ╚═══════╝                         ║
╚════════════════════════════════════════════╝

┌──────┐                        ┌──────┐
│ P1   │                        │ P5   │
│ ████ │                        │ ████ │
│Name  │   [GAME ARENA]        │Name  │
├──────┤                        ├──────┤
│ P2   │                        │ P6   │
│ ████ │   (Much larger         │ ████ │
│Name  │    visible area)       │Name  │
├──────┤                        ├──────┤
│ P3   │                        │ P7   │
│ ████ │                        │ ████ │
│Name  │                        │Name  │
├──────┤                        ├──────┤
│ P4   │                        │ P8   │
│ ████ │                        │ ████ │
│Name  │                        │Name  │
└──────┘                        └──────┘
```

**Key Differences**:
- ❌ Removed: Item counters (bomb/range/speed)
- ❌ Removed: Player alive counter
- ❌ Removed: Bottom-left stats panel
- ✅ Added: Round score tally with diamond icons
- ✅ Added: Player identifier portraits
- ✅ Added: Symmetrical left/right layout
- ✅ Result: ~40% more visible game area
