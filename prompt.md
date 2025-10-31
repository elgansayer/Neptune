# Bomberman Project Continuation Prompt

## Project Goal
To create a feature-rich, competitive, and fast-paced authoritative Bomberman-style game using Godot and Nakama. The core architectural pillars are low-latency gameplay and cheat prevention, with the goal of eventually supporting a wide array of modes and content suitable for a high-level e-sport.

---

## Long-Term Vision & Key Features

### Battle Mode (Multiplayer)
*   Supports up to 12 players in a single match.
*   Both local and online play are available.
*   Six different rulesets for battle: Survival Battle, Reversi Battle, Dodge Battle, Hyper Battle, King Battle, and Battle Royale.
*   Free-for-all and team matches are supported.

### Many Unique Stages / Arenas
*   More than 58 unique stages, each with distinct appearance and hazards.
*   Additionally 14 “Wide” stages (optimized for 9+ players) for larger battles.
*   Multiple variants and sizes of stages (standard vs wide).

### Score Mode & Single-Player Content
*   A “Score Mode” that acts like a remake of the classic Bomberman game, including a “Turbo” variant.
*   A “Battle Trial Mode” for single player: over 50 battle scenarios to clear.

### Power-Ups / Items / Characters
*   A large variety of pickups and power-ups drawn from many Bomberman games (e.g., Bomb Kick, Bomb Pass, Power Glove, Push, Bead Bomb, Cosplay).
*   673 characters selectable (and counting) — includes many cameos from across the Bomberman / Konami / Hudson history.

### Performance & Platform
*   Gamepad support.
*   Smooth 60 fps gameplay.
*   Available for Windows and macOS.

### Mod / Community Features
*   A freeware fan game with ongoing development.
*   Modding support for the community.
*   Customization / Stage Variants: Character skins, unlockable content, stage layout variants.

---

## Current Status
We have successfully set up the foundational architecture. The server and client are communicating, and a basic, networked game loop is in place.

**Completed Milestones:**
- **Nakama Server:** A TypeScript project is running on the server with a match handler that manages the authoritative game state.
- **Godot Client:** The client connects to the server, joins a match, and renders the game state using client-side prediction and server reconciliation.
- **Development Tools:** A `nakama-ctl` script is available to manage the server environment.

## Project Plan (Current Focus)

### Phase 1 & 2: Core Architecture (Largely Complete)
- [x] Setup Nakama TypeScript Project
- [x] Define the Game State & Loop
- [x] Implement Core Mechanics (Collision & Basic Explosions)
- [x] Implement Client-Side Prediction & Server Reconciliation

### Next Phase: Gameplay & Visual Polish
- [ ] Refine Client-Side Rendering (Current Task)
- [ ] Implement Power-ups
- [ ] Expand the Map System
- [ ] Expand the Character System

---

## Next Steps

The immediate next step is to improve the client-side rendering to enhance **game feel and visual clarity**, which are critical for competitive play.

**Suggested Action for Next Session:**

1.  **Create `Bomb.tscn`:** Create a scene for the bomb with a visual timer.
2.  **Update `GameManager.gd`:** Render bombs from the game state and improve explosion clarity.
3.  **Refine Player Visuals:** Add clear visual feedback for when a player is eliminated.
