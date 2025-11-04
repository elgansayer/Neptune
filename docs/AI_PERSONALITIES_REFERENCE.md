# AI Personalities Reference

Quick reference guide for all 9 bot personalities in the Bomberman AI system.

## Personality Comparison Table

| Personality | Aggression | Safety | Reaction Time | Bomb Frequency | Key Behavior |
|-------------|------------|--------|---------------|----------------|--------------|
| **Balanced** | ⚖️ 400 | ⚖️ 1000 | 50ms | 40% | Well-rounded, standard difficulty |
| **Aggressive** | 🔥 1000 | ⚠️ 700 | 20ms | 70% | Hunts opponents, high trap focus |
| **Timid** | 😰 100 | 🛡️ 2000 | 80ms | 20% | Avoids combat, safety first |
| **Greedy** | 💎 300 | ⚖️ 800 | 30ms | 45% | Power-up hunter, clears blocks |
| **Chaos** | 💥 900 | ⚠️ 600 | 10ms | 80% | Unpredictable, bombs constantly |
| **Defensive** | 🐢 50 | 🛡️ 2500 | 90ms | 15% | Wall hugger, extreme caution |
| **Kamikaze** | 💀 1500 | ⚠️ 200 | 5ms | 95% | Suicide bomber, trades kills |
| **Strategic** | 🧠 600 | 🛡️ 1200 | 40ms | 50% | Chess player, calculated moves |
| **Trapper** | 🕷️ 500 | ⚖️ 900 | 60ms | 30% | Ambush specialist, patient |

---

## Detailed Profiles

### 1. BALANCED (All-Rounder)
```
Aggression:    400  | Trap Bonus:    500
Safety:       1000  | Bomb Freq:    0.40
Reaction:      50ms | Escape Routes:  50
```
**Behavior:**
- Well-rounded in all aspects
- Transitions to HUNTING when opponents nearby
- Moderate bomb placement and safety awareness
- Good starter opponent for testing

**State Preferences:**
- 50% EXPLORING
- 25% HUNTING
- 15% ESCAPING
- 10% CORNERING

---

### 2. AGGRESSIVE (Hunter)
```
Aggression:   1000  | Trap Bonus:   1200
Safety:        700  | Bomb Freq:    0.70
Reaction:      20ms | Escape Routes:  30
```
**Behavior:**
- Actively seeks opponents within 7+ tiles
- Low bomb threshold (bombs frequently when near players)
- Fast reactions make it very responsive
- Values trapping more than block destruction

**State Preferences:**
- 40% HUNTING
- 30% CORNERING
- 20% ESCAPING
- 10% EXPLORING

**Special Traits:**
- Hunts from 7 tiles away
- Chases up to 10 tiles
- Quick corner executions (0.5s)

---

### 3. TIMID (Defensive Player)
```
Aggression:    100  | Trap Bonus:    150
Safety:       2000  | Bomb Freq:    0.20
Reaction:      80ms | Escape Routes: 150
```
**Behavior:**
- Rarely enters HUNTING state
- Focuses on EXPLORING and ESCAPING
- High bomb threshold (500) - only bombs high-value targets
- Maintains distance from opponents

**State Preferences:**
- 70% EXPLORING
- 25% ESCAPING
- 5% HUNTING
- <1% CORNERING

**Special Traits:**
- Never initiates combat
- Escapes at 2.5s danger threshold
- Stays in escape mode until 4.0s safe

---

### 4. GREEDY (Treasure Hunter)
```
Aggression:    300  | Trap Bonus:    350
Safety:        800  | Bomb Freq:    0.45
Reaction:      30ms | Escape Routes:  80
```
**Behavior:**
- Prioritizes EXPLORING for blocks and power-ups
- Uses `find_valuable_block_clusters()` extensively
- Bombs frequently to clear paths
- Will transition to POWER_UP_RUSH (when implemented)

**State Preferences:**
- 80% EXPLORING
- 10% ESCAPING
- 5% HUNTING
- 5% POWER_UP_RUSH (future)

**Special Traits:**
- Highest power-up value (1500)
- High exploration weight (500)
- Fast pathfinding updates (0.25s)

---

### 5. CHAOS (Unpredictable)
```
Aggression:    900  | Trap Bonus:    700
Safety:        600  | Bomb Freq:    0.80
Reaction:      10ms | Escape Routes:  25
```
**Behavior:**
- Bomb threshold is only 100 (lowest)
- Places bombs constantly, creating chaos
- Transitions rapidly between all states
- Fastest reactions (10ms) - appears precognitive

**State Preferences:**
- Rapid cycling through all states
- 30% EXPLORING
- 30% HUNTING
- 25% ESCAPING
- 15% CORNERING

**Special Traits:**
- Nearly instant reactions
- Very frequent bombs (80%)
- High aggression + high exploration = unpredictable

---

### 6. DEFENSIVE (Wall Hugger) 🆕
```
Aggression:     50  | Trap Bonus:    100
Safety:       2500  | Bomb Freq:    0.15
Reaction:      90ms | Escape Routes: 300
```
**Behavior:**
- Extreme safety priority (highest in game)
- Prefers corners and edges of map
- Only bombs when absolutely necessary
- Transitions to AMBUSHING after escapes (40% chance)

**State Preferences:**
- 60% AMBUSHING
- 30% EXPLORING
- 10% ESCAPING
- <1% HUNTING

**Special Traits:**
- Escapes at 2.5s danger (earliest)
- Stays safe until 4.0s threshold
- Requires 300 escape route value (multiple exits)
- Almost never hunts (needs aggression > 1500)
- Only chases if opponent within 3 tiles
- Patient ambusher (8s timeout)

---

### 7. KAMIKAZE (Suicide Bomber) 🆕
```
Aggression:   1500  | Trap Bonus:   2000
Safety:        200  | Bomb Freq:    0.95
Reaction:       5ms | Escape Routes:   0
```
**Behavior:**
- Willing to die for kills
- Chases opponents from 15+ tiles away
- Ignores danger during CORNERING state
- Positive proximity bonus (WANTS to be close to opponents)

**State Preferences:**
- 50% HUNTING
- 40% CORNERING
- 10% ESCAPING (only at last second)

**Special Traits:**
- Only escapes at 0.3s danger threshold (latest in game)
- Stays in CORNERING for 1.5s (ensures kill even if suicidal)
- Chases up to 20 tiles (never gives up)
- Nearly instant reactions (5ms)
- No escape route requirement (0)
- 95% bomb frequency (almost always bombing)

**Warning:** High risk of self-destruction - will trade 1-for-1 kills!

---

### 8. STRATEGIC (Chess Player) 🆕
```
Aggression:    600  | Trap Bonus:    900
Safety:       1200  | Bomb Freq:    0.50
Reaction:      40ms | Escape Routes: 150
```
**Behavior:**
- Calculated, measured decision-making
- Plans moves ahead (0.8s pathfinding frequency)
- Values power-ups strategically (800 value)
- Patient hunter with good survival instincts

**State Preferences:**
- 40% EXPLORING
- 30% HUNTING
- 20% ESCAPING
- 10% CORNERING

**Special Traits:**
- Hunts from 8 tiles (selective)
- Chases up to 12 tiles (persistent)
- Corners from 4 tiles away (plans ahead)
- Aggressive cornering (accepts 2 escape routes)
- Quick corner execution (0.3s - calculated)
- Moderate ambush patience (6s timeout)
- Good safety awareness without being timid

---

### 9. TRAPPER (Ambush Specialist) 🆕
```
Aggression:    500  | Trap Bonus:   1800
Safety:        900  | Bomb Freq:    0.30
Reaction:      60ms | Escape Routes: 100
```
**Behavior:**
- Extreme trap focus (highest trap bonus)
- Frequently enters AMBUSHING state (15% chance every 3s)
- Patient hunter - waits for perfect opportunity
- No idle penalty (comfortable waiting)

**State Preferences:**
- 50% AMBUSHING
- 30% EXPLORING
- 15% HUNTING
- 5% ESCAPING

**Special Traits:**
- Transitions to AMBUSHING after escapes (40% chance)
- 15% chance to ambush every 3s during exploration
- Extremely patient (10s ambush timeout)
- Sets up corners from 5 tiles away
- Prefers perfect traps (1 escape route only)
- Keeps distance for ambush (-300 proximity penalty)
- Selective bombing (30% frequency)
- Methodical pathfinding (0.4s updates)

**Playstyle:** "The Spider" - sets web of traps and waits

---

## Personality Selection Guide

### For New Players (Learning Mode)
- **Timid** - Easy to beat, won't pressure player
- **Defensive** - Passive, allows exploration

### For Practice (Medium Difficulty)
- **Balanced** - Standard opponent
- **Greedy** - Focuses on objectives, not combat
- **Strategic** - Predictable but competent

### For Challenge (Hard Mode)
- **Aggressive** - Will hunt you down
- **Trapper** - Sets elaborate traps
- **Strategic** - Smart and efficient

### For Chaos (Unpredictable)
- **Chaos** - Keeps you on your toes
- **Kamikaze** - High-risk, high-reward battles

### For Specific Testing
- **Defensive** - Test offensive strategies
- **Kamikaze** - Test defense and survival
- **Trapper** - Test awareness and escape skills
- **Strategic** - Test overall skill

---

## Recommended Bot Combinations

### Balanced Match (4 players)
- 1x Balanced
- 1x Aggressive
- 1x Greedy
- 1x Strategic

### Chaos Mode (4 players)
- 2x Chaos
- 1x Kamikaze
- 1x Aggressive

### Stealth Challenge (4 players)
- 2x Trapper
- 1x Defensive
- 1x Strategic

### Survival Mode (6 bots vs 1 human)
- 2x Aggressive
- 2x Strategic
- 1x Chaos
- 1x Kamikaze

### Variety Pack (8 players)
- 1x Balanced
- 1x Aggressive
- 1x Defensive
- 1x Greedy
- 1x Chaos
- 1x Strategic
- 1x Trapper
- 1x Human

---

## Technical Implementation Notes

### Reaction Time Impact
```
Kamikaze:    5ms  = ~200 decisions/sec (nearly precognitive)
Chaos:      10ms  = ~100 decisions/sec (instant)
Aggressive: 20ms  = ~50 decisions/sec  (pro player)
Strategic:  40ms  = ~25 decisions/sec  (good player)
Balanced:   50ms  = ~20 decisions/sec  (average player)
Trapper:    60ms  = ~16 decisions/sec  (observant)
Timid:      80ms  = ~12 decisions/sec  (cautious)
Defensive:  90ms  = ~11 decisions/sec  (very cautious)
```

### Auto-Spawn Configuration
Default 3-bot spawn (in `main_server.gd`):
```gdscript
spawn_ai_bot_local(AIPersonality.Type.BALANCED)
spawn_ai_bot_local(AIPersonality.Type.AGGRESSIVE)
spawn_ai_bot_local(AIPersonality.Type.TIMID)
```

### RPC Commands
```gdscript
# Spawn specific personality
request_spawn_bot(AIPersonality.Type.KAMIKAZE)
request_spawn_bot(AIPersonality.Type.TRAPPER)
```

---

## Future Enhancements

### Planned Personalities
- **Copycat** - Mimics human player style
- **Guardian** - Protects specific area
- **Berserk** - Becomes more aggressive when low HP

### Adaptive Behaviors
- Personalities adjust weights based on match progression
- Learn from player patterns during match
- Difficulty scaling based on player performance

### Team Mode Variants
- **Supporter** - Assists teammates
- **Leader** - Coordinates group strategies
- **Flanker** - Attacks from sides
