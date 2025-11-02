# Project Plan: Competitive Bomberman

**Core Architecture:**
*   **Server:** Nakama (TypeScript) will run the entire game simulation. It will be the single source of truth for all game logic, including player movement, bomb physics, and win/loss conditions. This is the **authoritative** part.
*   **Client:** Godot will be responsible for rendering the game state received from the server, capturing player input, and using client-side prediction to make the game feel responsive.

---

### Phase 1: Authoritative Server Logic (Nakama)

The goal of this phase is to create a complete, headless version of the game that runs on the server.

1.  **[x] Setup Nakama TypeScript Project:**
    *   Initialize a TypeScript project within the `nakama_server/modules` directory. This is where all our custom game logic will live.

2.  **[x] Define the Game State & Loop:**
    *   Create the main match handler script in TypeScript.
    *   Define the core `GameState` object (player positions, bomb states, grid data).
    *   Implement a fixed-tick-rate game loop (`match_loop`). This loop will advance the game simulation, process inputs, and broadcast the state to clients, ensuring consistent gameplay.

3.  **[x] Implement Core Mechanics (Server-Side):**
    *   **Player Movement:** Process movement inputs from clients to update player positions on the grid.
    *   **Bomb Placement:** Allow players to place bombs. The server will manage bomb timers.
    *   **Explosion Logic:** When a bomb's timer expires, the server calculates the explosion path, which players are hit, and which blocks are destroyed.

---

### Phase 2: Godot Client & Network Prediction

This phase focuses on making the Godot client a responsive window into the server's simulation.

1.  **[x] GameManager & State Sync:**
    *   Create a `GameManager.gd` script.
    *   It will listen for game state updates from the Nakama server (OpCode 2).
    *   When a new state is received, the `GameManager` will update all visual elements in the scene (players, bombs, walls) to match the server's authoritative state.

2.  **[x] Client-Side Prediction:**
    *   To make the game feel instant, when you press a movement key, the client will *immediately* move your player sprite. This is a "prediction".
    *   Simultaneously, the input is sent to the server.

3.  **[x] Server Reconciliation:**
    *   When the next game state update arrives from the server, it contains the *true* position of your player.
    *   The client will compare its predicted position with the server's true position. If they don't match (e.g., you tried to walk through a wall that you didn't know was there), the client will smoothly correct your player's position to what the server says. This prevents cheating and keeps all players in sync.

---

### Phase 3: Gameplay Features & Moddability

With the core network architecture in place, we can now easily add features.

1.  [x] Power-ups: Add logic to the server to spawn power-ups and apply their effects. The client will simply render them based on the server's state.
2.  [x] Map System: Design the `maps` folder to hold different tilemaps. The server will load a map at the start of a match and include it in the game state.
3.  [x] Character System: The `characters` folder will hold different player scenes. The server will assign a character to a player, and the client will display the correct visual representation.

---

### Phase 4: Sega Saturn Bomberman Features

This phase focuses on implementing the rich gameplay elements from the Sega Saturn version of Bomberman.

1.  **[ ] Expanded Multiplayer:**
    *   Increase the maximum player count to 10.
    *   Ensure the server and client can handle the increased number of players.

2.  **[ ] Game Modes:**
    *   **[ ] Story Mode:** Implement a single-player or cooperative campaign with multiple levels, objectives, and boss battles (e.g., Mad Bombers).
    *   **[ ] Battle Mode:** The classic Bomberman multiplayer experience. This will be the primary focus.
    *   **[ ] Master Mode:** A challenging single-player mode focused on completing levels as quickly as possible.

3.  **[ ] Items and Abilities:**
    *   **[ ] Basic Power-ups:**
        *   Bomb Up: Increase bomb capacity.
        *   Fire Up: Increase explosion radius.
        *   Speed Up: Increase movement speed.
        *   Geta: Decrease movement speed.
    *   **[ ] Special Abilities:**
        *   Bomb Kick: Kick bombs across the map.
        *   Power Gloves: Pick up and throw bombs.
        *   Bomb Pass: Walk through bombs.
        *   Wall Pass: Walk through soft blocks.
    *   **[ ] Special Bombs:**
        *   Remote Control: Detonate bombs manually.
        *   Gum Bomb
        *   Marble Bomb
        *   Power Bomb
        *   Penetration Bomb
    *   **[ ] Defensive Items:**
        *   Fire Suit: Temporary invulnerability to explosions.
        *   Heart: Extra life/hit point.
        *   1UP: Extra life.
    *   **[ ] Global Items:**
        *   Clock: Temporarily freezes enemies.

4.  **[ ] Dinosaur Helpers (Tirras):**
    *   **[ ] Egg Spawning:** Implement logic for eggs to spawn from destroyed blocks.
    *   **[ ] Tirra Mechanics:**
        *   Hatch from eggs and allow players to ride them.
        *   Provide an extra hit point.
        *   Implement growth levels (baby, adolescent, adult).
        *   Allow players to jump off.

5.  **[ ] Bonus System:**
    *   **[ ] Bonus Items:** Implement bonus items that grant points (e.g., Meat, Apples, Ice Cream).
    *   **[ ] Special Bonuses:** Implement special bonuses, like invincibility from collecting Meat while on a Tirra.

6.  **[ ] Interactive Stages:**
    *   Implement stage elements that can be interacted with, such as the slot machine cacti.

7.  **[ ] Online Play:**
    *   Implement modern online multiplayer using Nakama's features, ensuring a robust and feature-complete experience for up to 10 players.

---

### Phase 5: Power Bomberman Mod Support

*   [ ] Support every mod from Power Bomberman (https://gamebanana.com/tuts/15194)
*   [ ] Support their tools
*   [ ] Be able to load their characters and maps

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
