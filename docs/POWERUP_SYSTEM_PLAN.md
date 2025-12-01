# Bomberman Power-Up System Enhancement Plan

## Current Status: 90% Implemented

The power-up system already has:
- ✅ Server-side power-up spawning (ServerPowerUp class)
- ✅ Network sync of power-up positions & types
- ✅ Client-side rendering with animations (PowerUpRenderer)
- ✅ Player stat modification on collection
- ✅ Bomb Kicker ability (walk into bombs to kick)
- ✅ Power Glove ability (pick up + throw bombs)
- ✅ Power-up destruction by explosions
- ✅ 6 power-up types: BOMB_INCREASE, RANGE_INCREASE, SPEED_INCREASE, BOMB_KICKER, POWER_GLOVE, VIRUS

## Remaining Work

### 1. Map Power-Up Configuration
Extend map metadata in `game_instance.gd` to support:
```gdscript
powerup_config = {
    "drop_chance": 0.3,           # Chance per destroyed block
    "weights": {                   # Relative spawn weights
        "BOMB_INCREASE": 35,
        "RANGE_INCREASE": 30,
        "SPEED_INCREASE": 20,
        "BOMB_KICKER": 7,
        "POWER_GLOVE": 5,
        "VIRUS": 3
    },
    "disabled": ["VIRUS"],         # Types that won't spawn
    "predefined": [                # Guaranteed placements
        {"tile": [5, 5], "type": "POWER_GLOVE"}
    ]
}
```

### 2. PowerUpConfig Singleton
Create `shared/powerup_config.gd` with:
- Default drop rates
- Stat caps (max_bombs ≤ 8, bomb_range ≤ 6, speed_multiplier ≤ 2.0)
- Virus effect durations
- Map override loading

### 3. Virus Effects in ServerPlayer
Add virus state machine to `scripts/server_player.gd`:

| Effect | Description | Duration |
|--------|-------------|----------|
| DIARRHEA | Constant bomb dropping | 10s |
| CONSTIPATION | Can't place bombs | 10s |
| SLOW | 50% movement speed | 10s |
| SHORT_FUSE | Bombs explode in 1s | 10s |
| REVERSED_CONTROLS | Inverted movement | 10s |

### 4. New Power-Up Types
Extend `PowerUpType` enum in `scripts/server_powerup.gd`:

| Type | Effect |
|------|--------|
| LINE_BOMB | Place multiple bombs in a line |
| REMOTE_DETONATOR | Manual bomb detonation |
| PUNCH | Punch bombs forward |
| SHIELD | Temporary invincibility |

### 5. Stat Caps & Balance
Enforce in `collect_powerup()`:
- `max_bombs` capped at 8
- `bomb_range` capped at 6
- `speed_multiplier` capped at 2.0
- All configurable via PowerUpConfig

### 6. Client Virus Indicators
Add visual effects in `client/game_view.gd`:
- Skull overlay on infected players
- Color tint based on virus type
- Synced via player state dictionary

## Design Decisions Needed

1. **Predefined vs Random Spawns**
   - Maps can have guaranteed power-ups at specific tiles
   - OR purely weighted random from destroyed blocks
   - Recommendation: Support both via `predefined` array

2. **Virus Passing**
   - Classic SNES: Viruses pass to other players on contact
   - Adds strategic depth but more complexity
   - Decision: TBD

3. **Power-Up Despawn**
   - Should power-ups despawn after 30-60 seconds?
   - Prevents late-game clutter
   - Decision: TBD

## File Locations

| Component | File |
|-----------|------|
| Server power-up | `scripts/server_powerup.gd` |
| Server player | `scripts/server_player.gd` |
| Game instance | `game_instance.gd` |
| Client renderer | `client/effects/powerup_renderer.gd` |
| Power-up assets | `res/items/sbomberman/` |
| Config singleton | `shared/powerup_config.gd` (to create) |
