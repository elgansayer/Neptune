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