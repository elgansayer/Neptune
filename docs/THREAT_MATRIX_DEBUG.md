# Threat Matrix Visualization

## Overview

The threat matrix visualization is a debug overlay that shows the AI system's danger awareness in real-time. It displays which tiles are threatened by bomb explosions and when they will become lethal.

## How to Use

1. **Start the game** with bots enabled
2. **Press F3** to toggle the threat matrix visualization on/off
3. Watch as tiles light up with different colors based on threat level

## Color Coding

| Color | Meaning | Time Until Explosion |
|-------|---------|---------------------|
| 🔴 **Red** | Immediate danger | < 500ms |
| 🟠 **Orange** | High danger | 500ms - 1500ms |
| 🟡 **Yellow** | Warning | 1500ms - 3000ms |
| 🟢 **Green** | Safe/distant | > 3000ms or safe |

## What You'll See

- **Solid colored tiles**: Areas that will be hit by bomb explosions
- **Time countdown**: For urgent threats (< 2 seconds), the remaining time is shown on the tile
- **Real-time updates**: The visualization updates every frame as bombs tick down
- **Chain reactions**: When bombs trigger other bombs, you'll see the threat matrix update to show the chained explosions

## How Bots Use This

Bots use the threat matrix to:
1. **Evaluate safety** before planting bombs
2. **Find escape routes** after planting
3. **Avoid dangerous areas** during navigation
4. **Plan optimal bomb placement** for maximum effect

## Technical Details

The threat matrix is calculated on the server every physics frame and includes:
- All active bombs with their remaining fuse time
- Explosion patterns respecting walls (hard walls stop blasts)
- Chain reaction simulation (bombs triggering other bombs)
- Exact detonation times in milliseconds

When a bot plants a bomb, it simulates adding that bomb to the threat matrix to evaluate escape routes before committing to the placement.

## Verification

You can use this visualization to verify:
- ✅ Blast patterns are correct (explosions stop at hard walls)
- ✅ Timing calculations are accurate
- ✅ Chain reactions are properly simulated
- ✅ Bots are correctly identifying safe vs. dangerous tiles
- ✅ Escape routes lead to tiles NOT in the threat matrix

## Performance

The visualization has minimal performance impact when disabled (default). When enabled, it draws colored rectangles over threatened tiles, which is very lightweight.
