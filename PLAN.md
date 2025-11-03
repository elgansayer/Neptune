# Project Plan: Competitive Bomberman

**Updated: November 2025**

## 🏗️ Current Architecture (v2.0)

### Core Design Philosophy
- **Server:** Pure Godot headless server running authoritative game logic
- **Client:** Godot client for rendering and input
- **Backend:** Abstract interface ready for PlayFab/Nakama integration
- **Physics:** Native Godot physics engine (CharacterBody2D, StaticBody2D)

### Why This Architecture?

**Previous Attempt (v1.0):**
- Used Nakama TypeScript server with manual collision detection
- Required implementing physics from scratch in TypeScript
- Complex physics (throwing bombs, bouncing) would be very difficult

**Current Approach (v2.0):**
- Pure Godot server with built-in physics engine
- Can use `move_and_slide()`, collision exceptions, `apply_impulse()` natively
- Easy to add throwing, kicking, bouncing mechanics later
- PlayFab/Nakama used only for meta-game (accounts, matchmaking, leaderboards)

### Project Structure
```
bomberman/
├── client/              # Client-only code
│   ├── ui/              # Menus, HUD
│   ├── prediction/      # Client prediction (future)
│   └── main_client.gd   # Client entry point
├── server/              # Server-only code  
│   ├── auth/            # Authentication (local for now)
│   ├── lobby/           # Lobby/matchmaking
│   ├── game_instance.gd # Game logic manager
│   └── main_server.gd   # Server entry point
└── shared/              # Code used by both
    ├── entities/        # Player, Bomb, Powerup scenes
    ├── game_logic/      # Core game rules
    ├── maps/            # Map data
    ├── constants.gd     # Game constants
    └── backend_service.gd  # Abstract backend interface
```

---

## ✅ Completed Phases

### Phase 1: Foundation ✅
- [x] Server-authoritative Godot architecture
- [x] ENet networking (client-server)
- [x] RPC-based input handling
- [x] Abstract backend interface for PlayFab migration
- [x] Temporary local authentication (will be replaced)

### Phase 2: Core Game Mechanics ✅
- [x] Player movement with `CharacterBody2D` and `move_and_slide()`
- [x] Bomb placement with `StaticBody2D`
- [x] Collision exception system (walk out of bombs)
- [x] Bomb explosions with multi-directional propagation
- [x] Player death on explosion hit
- [x] Server state synchronization (20Hz)

---

## 🚧 Current Phase: Polish & Multiplayer

### Phase 3: Visual Polish & Multiple Players

### Phase 3: Visual Polish & Multiple Players

1.  **[ ] Proper Sprites and Animations:**
    *   Replace icon.svg placeholders with actual character sprites
    *   Add walking animations (4 directions)
    *   Add bomb sprite and animation
    *   Add explosion effects and animations

2.  **[ ] Map Rendering:**
    *   Render the tile-based map (walls, destructible blocks)
    *   Add background/floor tiles
    *   Support multiple map themes

3.  **[ ] Multiple Players in One Game:**
    *   Support 2-10 players in a single game instance
    *   Spawn players at different starting positions
    *   Color-code players for easy identification
    *   Show player names above sprites

4.  **[ ] Lobby System:**
    *   Create/join game rooms
    *   Ready-up system
    *   Room configuration (map selection, max players, game mode)
    *   Kick/ban functionality for hosts

---

### Phase 4: Gameplay Features & Polish

1.  **[ ] Client-Side Prediction:**
    *   Predict local player movement for instant feedback
    *   Server reconciliation when predictions are wrong
    *   Smooth interpolation for other players

2.  **[ ] Destructible Blocks:**
    *   Spawn destructible blocks on map
    *   Destroy blocks with explosions
    *   Drop power-ups from destroyed blocks

3.  **[ ] Power-ups:**
    *   Bomb Up: Increase max bombs
    *   Fire Up: Increase explosion range
    *   Speed Up: Increase movement speed
    *   Implement power-up collection and effects

4.  **[ ] Game Modes:**
    *   Free-for-all (last player standing)
    *   Team battle
    *   Timed matches
    *   Score-based matches

5.  **[ ] Win Conditions & Respawn:**
    *   Detect when match ends
    *   Display winner
    *   Optional respawn system
    *   Post-match statistics

---

### Phase 5: Advanced Features

1.  **[ ] Special Bombs and Abilities:**
    *   Bomb Kick: Kick bombs across the map
    *   Power Gloves: Pick up and throw bombs
    *   Remote Control: Detonate bombs manually
    *   Bomb Pass: Walk through bombs
    *   Wall Pass: Walk through soft blocks

2.  **[ ] Advanced Bomb Types:**
    *   Remote bombs
    *   Power bombs (larger explosion)
    *   Penetration bombs (go through walls)

3.  **[ ] Map Hazards:**
    *   Moving obstacles
    *   Shrinking playfield
    *   Environmental hazards

---

### Phase 6: Backend Integration

1.  **[ ] PlayFab Integration:**
    *   Replace LocalBackend with PlayFabBackend
    *   Player authentication via PlayFab
    *   Leaderboards
    *   Player statistics tracking
    *   Inventory system for cosmetics

2.  **[ ] Matchmaking:**
    *   Skill-based matchmaking
    *   Quick play
    *   Ranked mode
    *   Custom games

---

### Phase 7: Sega Saturn Bomberman Features

This phase focuses on implementing the rich gameplay elements from the Sega Saturn version.

1.  **[ ] Expanded Multiplayer:**
    *   Support up to 10 players
    *   Spectator mode

2.  **[ ] Dinosaur Helpers (Tirras):**
    *   Eggs spawn from destroyed blocks
    *   Players can ride Tirras for extra abilities
    *   Growth levels (baby, adolescent, adult)

3.  **[ ] Story Mode:**
    *   Single-player campaign
    *   Boss battles
    *   Cooperative mode

4.  **[ ] Interactive Stages:**
    *   Stage-specific mechanics (e.g., slot machines, moving platforms)

---

### Phase 8: Power Bomberman Mod Support

### Phase 8: Power Bomberman Mod Support

*   [ ] Support every mod from Power Bomberman (https://gamebanana.com/tuts/15194)
*   [ ] Support their tools
*   [ ] Be able to load their characters and maps

---

## 📚 Reference Material

### SBomberman
A previous client-authoritative peer-to-peer Bomberman implementation. Located at `/SBomberman/`.

**Use for:**
- Movement feel and game mechanics reference
- Bomb placement patterns
- Explosion logic ideas
- Corner assistance/wall sliding

**Don't copy:**
- Networking architecture (peer-to-peer vs our client-server)
- State management patterns
- Trust model assumptions

See `docs/SBOMBERMAN_REFERENCE.md` for detailed comparison.

---

## 🎯 Current Status

### What Works ✅
- Server-authoritative Godot physics
- Player movement with collision
- Bomb placement with collision exceptions
- Bomb explosions with player death
- Multiple game instances
- Basic networking and state sync

### What's Next 🚀
1. Add proper sprites and animations
2. Render the map visually
3. Support multiple players in one game
4. Add destructible blocks and power-ups
5. Build lobby system

### Future Integration 🔮
- PlayFab for accounts, matchmaking, leaderboards
- SQLite for local data persistence
- Advanced physics (throwing/kicking bombs)

---

### Player Stats

#### 🎮 Core Gameplay Stats

**General Performance**

*   Matches Played
*   Matches Won
*   Matches Lost
*   Win Rate (%)
*   Average Match Length
*   Fastest Win (time)
*   Longest Survival Time
*   Average Placement (in free-for-all matches)

**Round Stats**

*   Rounds Played
*   Rounds Won
*   Round Win Rate (%)
*   Average Rounds per Match

**Bomb Usage**

*   Total Bombs Placed
*   Bombs Placed per Match
*   Bombs Detonated by Player
*   Bombs Triggered by Chain Reaction
*   Bombs Exploded by Other Players’ Flames
*   Bombs That Killed Player (self-KOs)
*   Average Bombs Active at Once

**Kills**

*   Total Kills
*   Kills per Match
*   Kills per Minute
*   Multi-Kills (2+, 3+, 4+ in one explosion)
*   Chain Reaction Kills
*   Environmental Kills (e.g., by triggering something)
*   Suicide Kills (self-bombing)
*   Assists (setting up a kill that another player finished)

**Deaths**

*   Total Deaths
*   Deaths by Own Bombs
*   Deaths by Opponent Bombs
*   Deaths by Environmental Hazards
*   Times Crushed by Walls (if stage shrinking mechanic)
*   Average Death Time (time survived before death)

#### ⚡ Power-Up Stats

**Power-Up Collection**

*   Total Power-Ups Collected
*   Power-Ups Missed (visible but uncollected)
*   Most Collected Power-Up Type
*   Power-Up Collection Rate (collected ÷ spawned)
*   Time to First Power-Up (per match)

**By Type**

*   Fire Power-Ups Collected
*   Bomb Power-Ups Collected
*   Speed Power-Ups Collected
*   Remote Bombs Collected
*   Kick Power-Ups Collected
*   Punch Power-Ups Collected
*   Glove Power-Ups Collected
*   Dangerous Bombs Collected
*   Special/Unique Power-Ups Collected

**Usage**

*   Kicks Performed
*   Punches Thrown
*   Bombs Thrown (via glove)
*   Remote Bombs Detonated
*   Bombs Kicked into Enemies
*   Bombs Caught and Re-Thrown

#### 🧠 Skill and Efficiency Stats

**Strategy**

*   Bomb Placement Accuracy (kills ÷ bombs placed)
*   Time Between Bomb Placement and Kill (average)
*   Number of Kills Without Power-Ups
*   Average Time Alive per Round
*   Average Distance Moved Before Death
*   Average Opponents Eliminated Before Death

**Efficiency**

*   Bombs per Kill Ratio
*   Power-Ups per Kill Ratio
*   Movement per Kill (tiles moved ÷ kills)
*   Damage Dealt (if partial damage is tracked)
*   Efficiency Rating (custom composite stat)

#### 💣 Combat Behavior

**Aggression**

*   Offensive Bombs Placed (near opponents)
*   Defensive Bombs Placed (to block)
*   Time Spent in Combat (near other players)
*   Times Forced Opponent into Trap
*   Area Controlled by Player (tiles dominated over time)

**Evasion**

*   Bomb Explosions Dodged
*   Frames Between Explosion Start and Evade
*   Successful Escapes from Enclosed Situations
*   Average Distance from Nearest Explosion

**Tactics**

*   Times Player Used Bomb Chains Intentionally
*   Opponents Eliminated by Chain Reaction
*   Players Eliminated Using Thrown Bombs
*   Traps Successfully Executed (placed bomb that trapped opponent)

#### 🏆 Ranking and Achievements

**Competitive Metrics**

*   Current Rank / Tier
*   Matchmaking Rating (MMR)
*   Highest Rank Achieved
*   Longest Win Streak
*   Longest Lose Streak
*   Win Rate vs. Higher Ranked Players
*   Win Rate vs. Lower Ranked Players

**Achievements**

*   “Flawless” Wins (no deaths)
*   “Comeback” Wins (won after being last alive)
*   “Pacifist” Wins (won without kills)
*   “Explosive Expert” (highest bomb kill ratio)
*   “Speed Demon” (most power-ups collected early)
*   “Survivor” (last player alive most times)

#### 🗺️ Map & Mode Stats

**Map Performance**

*   Matches Played per Map
*   Win Rate per Map
*   Favorite Map
*   Least Successful Map
*   Average Survival Time per Map

**Game Mode Performance**

*   Matches Played per Mode (e.g., FFA, Team, Ranked, Classic)
*   Win Rate per Mode
*   Kills per Mode
*   Average Placement per Mode

#### 👥 Team Play Stats (if team modes exist)

*   Team Matches Played
*   Team Wins
*   Team Win Rate
*   Assists per Match
*   Friendly Fire Incidents
*   Revives (if allowed)
*   Times Saved a Teammate
*   Most Common Teammate
*   Team Synergy Rating (average performance with teammates)

#### 📈 Progression Stats

*   Experience Earned
*   XP per Match
*   XP per Minute
*   Lifetime XP
*   Level / Prestige
*   Total Play Time
*   Time in Menu vs Time in Battle
*   Matches Played per Day (average)

#### 🎨 Style and Customization Stats

*   Favourite Character / Skin
*   Favourite Bomb Type
*   Favourite Explosion Effect
*   Most Used Emote
*   Most Used Victory Pose
*   Outfit Changes Made
*   Custom Loadouts Created

#### 🧩 Meta / Behavioural Stats

*   Disconnects / Quits
*   Reconnects
*   AFK Time
*   Reports Filed Against Player
*   Reports Received
*   Matches with Perfect Connection
*   Ping Average / Stability

#### 🔥 Advanced Analytics (for competitive dashboards)

*   Heatmap of player movement per map
*   Average “threat zone” radius (how far others avoid player)
*   Reaction time to explosions
*   Kill-to-Death differential (K/D ratio)
*   Kill participation rate (in team modes)
*   Most common opponent killed
*   Most common opponent killed by
*   Session Consistency (variance in performance)

#### 📊 Fun / Cosmetic Stats

*   Total Blocks Destroyed
*   Blocks Destroyed per Match
*   Crates Blown Up
*   Times Picked Up by Explosion but Survived
*   Bombs Kicked Off Map
*   Matches Won Wearing a Costume
*   Total Explosions Witnessed
*   “Lucky Escapes” (survived with <0.5s left before explosion)



1. Latency Mitigation & Compensation

These techniques help to hide or correct for network delay (latency) to make the game feel more responsive.

Lag Compensation (Server-Side Rewind):

The server stores a history of recent game states (e.g., player positions).

When a player's action (like a shot) arrives, the server 'rewinds' the game world for that player to the time the action was made on their client.

This ensures that hits register where the player saw them on their screen, making the experience feel fairer and more immediate.

Client-Side Prediction:

The client immediately simulates the result of a local player's input (e.g., movement, ability use) without waiting for server confirmation.

This provides instant feedback to the player, making controls feel responsive.

Server Reconciliation (Correction):

The server remains the final authority on the game state.

The client's prediction is occasionally corrected by authoritative updates from the server.

The client then 'reconciles' its state, often by re-simulating inputs from the time of the server update to the present, or by blending the predicted and corrected positions smoothly.

Interpolation:

Clients buffer a few recent updates from the server for remote entities (other players, objects).

The client displays the remote entities at a calculated position between two received updates, based on a fixed delay (usually $\approx 100\text{ms}$).

This makes remote movement look smooth instead of jerky, as it compensates for varying update rates and network jitter.

2. State & Bandwidth Optimisation

These methods reduce the amount of data sent over the network, lowering bandwidth use and often latency.

Dead Reckoning (Extrapolation):

When a client hasn't received an update for a remote entity, it predicts the entity's future position based on its last known position, velocity, and direction.

This is typically used in conjunction with interpolation to 'guess' where an object is until the next authoritative update arrives, preventing stops and starts.

Delta Compression/Updates:

Instead of sending the entire game state or object data in every packet, only send the changes (the "delta") from the last sent state.

This drastically reduces packet size.

Bit Packing / Quantisation:

Using the minimum number of bits required to represent data (e.g., using 4 bits for a value that only ranges from 0-15 instead of a full byte).

Quantisation reduces floating-point precision to represent positions and rotations with fewer bits.

Interest Management:

Servers only send updates for game objects that are relevant to a specific client. For example, a player in one area of a massive game map doesn't need updates about actions taking place on the other side of the map.

Compression Algorithms:

Using lossless compression (like Huffman coding or specialised game compression libraries) on the network packets before sending them to reduce the data size.

3. Protocol & Control

These relate to how data is transmitted and prioritised.

UDP (User Datagram Protocol):

Used for most real-time, time-critical game data (e.g., player movement, shooting). It's fast because it does not guarantee delivery or ordering, which is acceptable since outdated data is often useless anyway.

TCP (Transmission Control Protocol):

Used for less time-critical, but essential, data (e.g., chat, login, initial world data). It guarantees delivery and order but introduces more latency.

Traffic Prioritisation (Quality of Service - QoS):

Network administrators or specialised software can mark game traffic as high priority, ensuring it gets preference over other network traffic (like streaming or downloads).

Dedicated Server Infrastructure:

Using servers specifically designed for gaming, often geographically distributed, to minimise the physical distance data has to travel (reducing latency).

Server Tick Rate:

The frequency (e.g., 60 times per second) at which the server updates the game state. A higher tick rate generally means more precise and smooth gameplay, especially for fast-paced games.