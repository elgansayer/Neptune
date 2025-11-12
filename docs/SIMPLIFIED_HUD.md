# Simplified HUD Implementation for 9/10-Player Widescreen Battle Mode

## Overview
This HUD is designed for minimal obstruction during large multiplayer battles (9-10 players), based on classic Sega Saturn Bomberman's widescreen battle mode aesthetic.

## Visual Layout

```
╔════════════════════════════════════════════════════════════════════════════╗
║  ◆◆◆           ╔═══════════════╗           ◆◆◆                            ║
║  Left Score    ║    3:00      ║    Right Score                             ║
║  Tally         ╚═══════════════╝    Tally                                  ║
╚════════════════════════════════════════════════════════════════════════════╝

┌──────┐                                                           ┌──────┐
│ P1   │                                                           │ P6   │
│ ██   │                                                           │ ██   │
│Name  │               [Game Action Area]                         │Name  │
├──────┤                                                           ├──────┤
│ P2   │                                                           │ P7   │
│ ██   │                                                           │ ██   │
│Name  │                                                           │Name  │
├──────┤                                                           ├──────┤
│ P3   │                                                           │ P8   │
│ ██   │                                                           │ ██   │
│Name  │                                                           │Name  │
├──────┤                                                           ├──────┤
│ P4   │                                                           │ P9   │
│ ██   │                                                           │ ██   │
│Name  │                                                           │Name  │
├──────┤                                                           ├──────┤
│ P5   │                                                           │ P10  │
│ ██   │                                                           │ ██   │
│Name  │                                                           │Name  │
└──────┘                                                           └──────┘
```

## Components

### 1. Time Limit (Top Center)
- **Location**: Top center, above playing field
- **Format**: Digital `M:SS` format (e.g., `3:00` → `0:00`)
- **Font Size**: 36px
- **Colors**:
  - White (>60 seconds)
  - Yellow (60-30 seconds)
  - Red (<30 seconds)
- **Styling**: Black shadow (2px offset) for high visibility

### 2. Round Score Tally (Flanking Timer)
- **Location**: Left and right of timer at top
- **Visual**: Diamond-shaped icons (◆)
- **Size**: 16x16 pixels
- **Color**: Player's assigned color
- **Purpose**: Each diamond represents one round won by that player
- **Layout**: Horizontal row, 4px spacing between icons

### 3. Player Identifiers (Edge Panels)
- **Location**: Vertical columns on extreme left and right edges
- **Size**: 60x70 pixels per portrait
- **Components**:
  - Colored square (40x40px) representing player
  - Player name (truncated to 8 chars, 10px font)
- **Border**: 2px border using player's color
- **Background**: Dark grey panel (RGB: 26, 26, 38, 90% opacity)
- **Spacing**: 8px between portraits

## Color Palette

### Background Colors
- Top Bar Panel: `rgba(26, 26, 38, 0.95)` - Dark grey/black
- Player Portraits: `rgba(38, 38, 51, 0.9)` - Slightly lighter dark grey
- Border: `rgb(77, 102, 128)` - Teal/grey

### Player Colors (for identifiers and score icons)
1. White: `rgb(255, 255, 255)`
2. Black: `rgb(51, 51, 51)`
3. Red: `rgb(255, 51, 51)`
4. Blue: `rgb(51, 102, 255)`
5. Yellow: `rgb(255, 204, 51)`
6. Green: `rgb(51, 255, 51)`
7. Pink: `rgb(255, 102, 204)`
8. Purple: `rgb(153, 51, 255)`
9. Orange: `rgb(255, 153, 51)`
10. Cyan: `rgb(51, 255, 255)`

### Timer Colors
- Normal: `rgb(255, 255, 255)` - Bright white
- Warning: `rgb(255, 204, 0)` - Bright yellow
- Critical: `rgb(255, 77, 77)` - Bright red

## Font Style
- **Style**: Clean, blocky digital font
- **Characteristics**:
  - No anti-aliasing (pixel-perfect)
  - High contrast against background
  - Centrally aligned
  - Black shadow for depth
- **Timer**: 36px
- **Player Names**: 10px

## Key Design Principles

### Minimal Obstruction
- No item counters (bomb count, range, speed) displayed
- HUD elements positioned at extreme edges
- Central play area remains completely clear
- Transparent backgrounds allow gameplay visibility

### High Contrast
- Bright text on dark backgrounds
- Black shadows on all text for readability
- Player colors are vibrant and distinct
- Border colors complement without overwhelming

### Retro Aesthetic
- Blocky, pixelated appearance
- Flat color panels (no gradients)
- Sharp corners with minimal rounding (4px radius)
- Digital timer format matches classic games

### Scalability
- Supports 2-10 players
- Player identifiers auto-distribute between left/right panels
- Score tally icons auto-arrange horizontally
- Responsive to different screen widths

## Implementation Details

### Files Modified
1. `client/ui/game_hud.gd` - HUD logic and styling
2. `client/ui/game_hud.tscn` - Scene layout
3. `client/game_view.gd` - Integration with game state
4. `themes/hud_panel_style.tres` - Panel styling resource

### Key Methods
- `update_timer(time_remaining: float)` - Updates match timer with color warnings
- `update_round_scores(player_scores: Dictionary)` - Creates diamond icons for round wins
- `update_player_identifiers(players: Dictionary)` - Creates/updates player portraits
- `create_score_icon(color: Color)` - Generates diamond-shaped score icon
- `create_player_portrait(player_id, player_data)` - Generates player identifier panel

### Data Requirements
The HUD expects the following data from the game state:
- `match_timer: float` - Time remaining in seconds
- `players: Dictionary` - Player data including username and color
- `round_scores: Dictionary` - Optional, maps player_id to rounds won

## Differences from Standard HUD

### Removed Elements
- ❌ Bomb count display
- ❌ Flame range indicator
- ❌ Speed multiplier display
- ❌ Player alive counter (replaced with visible portraits)
- ❌ Bottom-left stats panel

### Added Elements
- ✅ Round score tally with diamond icons
- ✅ Visual player identifiers with colors
- ✅ Enhanced timer visibility
- ✅ Symmetrical left/right layout

## Testing Notes

To test this HUD:
1. Run a game with 4+ players to see player portrait distribution
2. Verify timer color changes at 60s and 30s thresholds
3. Test round score display with mock data
4. Ensure no overlap with gameplay area
5. Verify readability on different background colors

## Future Enhancements

Potential improvements for later:
- Add character portraits instead of colored squares
- Animate round score icons when awarded
- Add death indicator overlay on player portraits
- Support team colors in team battle modes
- Add mini-map in corner for very large arenas
