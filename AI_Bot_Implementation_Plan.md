# AI Bot Implementation Plan

## 1. Overview

### Existing Architecture Summary

The current Bomberman project is built on a robust client-server architecture using a headless Godot server. This design is ideal for authoritative AI, as all game logic and physics are processed on the server, preventing client-side cheating and ensuring consistent behavior.

- **Networking**: ENet-based RPC communication between client and server.
- **Game Logic**: The `server/game_instance.gd` script manages the lifecycle of a single match, including player management and state updates.
- **Player Control**: Player input is sent from the client to the server, which then moves the `CharacterBody2D` node for the player.
- **State Synchronization**: The server broadcasts game state to all clients at a rate of 20Hz.
- **Backend**: An abstract `BackendService` is in place, currently using a `LocalBackend`, with plans for PlayFab/Nakama integration. This is relevant for potentially storing bot statistics or using a backend service to manage bot populations in matchmaking.

Currently, there is no AI implementation. All players are human-controlled.

### Purpose and Design Goals

The goal is to introduce **Hybrid AI Bomberman Bots** that are both challenging and feel human-like. They should serve as formidable opponents for single-player modes and be able to fill empty slots in multiplayer matches.

**Design Goals:**
- **Challenging but Fair**: Bots should be skilled but make believable mistakes.
- **Human-Like Behavior**: Avoid robotic, perfect movements. Introduce slight delays, varied strategies, and occasional "errors" in judgment.
- **Scalable**: The AI system should be efficient enough to run multiple bots in a 10-player match without significant performance overhead.
- **Adaptive**: The hybrid model will allow bots to react to the changing game state dynamically, weighing risks and rewards.

## 2. Architecture Plan

### Integration Strategy

AI bots will be treated as server-side players. They will not have a client connection. The server's `GameInstance` will be responsible for creating, managing, and processing the AI bots. From the perspective of human players' clients, a bot is indistinguishable from another human player, as they only receive state updates from the server.

1.  **Instantiation**: When a game needs a bot, the `GameInstance` will instantiate an `AIBot` scene.
2.  **Management**: The `GameInstance` will hold a reference to each bot and call its `update_ai()` function on each physics tick.
3.  **Synchronization**: The bot's position and actions (placing bombs) will be part of the regular game state snapshot that is sent to all human clients.

### Proposed Node/Class Hierarchy

We will create a new `AIBot` class that inherits from the existing `Player` class if there is one, or from `CharacterBody2D` and shares common components.

```
- Player (CharacterBody2D)
  - player.gd (handles input from network)
  - ...

- AIBot (extends Player)
  - AIBotController.gd (contains the core decision-making logic)
  - AIObserver.gd (component for reading and interpreting game state)
  - ...
```

**`AIBotController.gd`**: This script will be the "brain" of the bot. On every server physics frame, it will:
1.  Observe the game state via the `AIObserver`.
2.  Process the state through the hybrid decision-making system.
3.  Translate the chosen action into player input (e.g., setting `velocity` and triggering a `place_bomb` event).

**`AIObserver.gd`**: This helper class will be responsible for reading the game world and converting it into a simplified representation that the AI can use. It will provide answers to questions like:
- "What is the layout of the map (walls, breakable blocks)?"
- "Where are the bombs and when will they explode?"
- "Where are the safe zones?"
- "Where are the opponents and power-ups?"

## 3. Decision-Making System (Hybrid Approach)

We will use a **Utility-Based AI** system. This approach assigns a numerical score (utility) to various possible actions, and the AI chooses the action with the highest score. This is a flexible and powerful alternative to a complex state machine and serves as a great foundation before moving to more advanced ML models.

The core idea is to evaluate the utility of moving to each adjacent, reachable tile.

### Utility-Driven Layer (The "Brain")

For each accessible tile around the bot, we calculate a score based on several factors:

-   **Safety Score**:
    -   `+1000` if the tile is safe from any current or future explosions.
    -   `-10000` if the tile is currently in an explosion path. The high negative value makes survival the top priority.
-   **Power-up Score**:
    -   `+500` if the tile contains a desirable power-up. The score can be weighted by the power-up type (e.g., Bomb Range > Speed).
-   **Aggression Score**:
    -   `+300` if placing a bomb on the current tile could trap an opponent. This is determined by checking if an opponent is in a dead-end path that would be blocked by the new bomb.
-   **Exploration Score**:
    -   `+100` for moving towards breakable blocks. This encourages the bot to clear the map and find power-ups.
-   **Escape Route Score**:
    -   `+50` for tiles that have more than one exit, encouraging bots to avoid getting trapped.
-   **Penalty Score**:
    -   `-200` for moving closer to an opponent without a clear objective.
    -   `-50` for staying idle.

The bot calculates the total utility for each potential move and chooses the one with the highest score.

### Rule-Based Layer (Core Tactics)

This layer provides immediate, high-priority actions that can override the utility calculations in critical situations.

-   **Immediate Bomb Threat**: If the bot is currently on a tile that will explode, its ONLY goal is to find the nearest safe tile. All other utility calculations are ignored.
-   **Bomb Placement Logic**: A bot will only place a bomb if:
    1.  It has a clear escape route.
    2.  It's trying to break blocks or trap a player.
    3.  It won't trap itself.

### Data Flow

1.  **Observe**: The `AIObserver` scans the game grid, creating a data structure representing the current state (bomb timers, player positions, wall locations). It also pre-calculates a "danger map" of all tiles that will be affected by explosions.
2.  **Evaluate**: The `AIBotController` iterates through reachable tiles. For each tile, it calculates the utility score using the hybrid rules.
3.  **Act**: The bot commits to the action (e.g., move towards the highest-scoring tile, place a bomb) and the `AIBot` node executes it.

## 4. Technical Implementation Details

### Recommended Libraries

For this initial implementation, we will rely entirely on **built-in Godot features**.
-   **Pathfinding**: Godot's `AStar2D` or `AStarGrid2D` is perfect for finding paths to power-ups or escape routes. The `AIObserver` will build the A* graph on the fly based on the current map state.
-   **No ML Libraries Needed (Yet)**: A utility-based system requires no external machine learning libraries like TensorFlow. This keeps the implementation simple and performant.

### Pseudocode for Decision Loop

```gdscript
# In AIBotController.gd

func _physics_process(delta):
    # 1. Observe
    var game_state = observer.get_world_state()
    var current_tile = map.world_to_map(global_position)

    # 2. Rule-Based Override (Survival First)
    if game_state.is_tile_in_danger(current_tile):
        var escape_path = pathfinder.find_path_to_nearest_safe_tile(current_tile, game_state)
        if not escape_path.is_empty():
            move_towards(escape_path[1]) # Move to the next tile in the path
            return

    # 3. Utility-Driven Evaluation
    var best_move = null
    var highest_utility = -INF

    for tile in get_adjacent_reachable_tiles(current_tile):
        var utility = calculate_utility_for_tile(tile, game_state)
        if utility > highest_utility:
            highest_utility = utility
            best_move = tile

    # 4. Act
    if best_move:
        move_towards(map.map_to_world(best_move))

    # Decide whether to place a bomb
    if should_place_bomb(current_tile, game_state):
        place_bomb()

func calculate_utility_for_tile(tile, game_state):
    var score = 0
    # Safety
    if game_state.is_tile_in_danger(tile):
        score -= 10000
    else:
        score += 1000
    
    # Power-ups
    if game_state.has_powerup(tile):
        score += 500

    # Aggression
    if can_trap_opponent_from(tile, game_state):
        score += 300
        
    # ... and so on for other factors
    return score
```

## 5. Performance and Networking

-   **Server-Side Logic**: All AI calculations will run on the server. This is crucial for security and consistency.
-   **Optimization**: The `AIObserver`'s world representation should be efficient. The "danger map" should be calculated once per frame and shared among all bots. Pathfinding can be computationally expensive, so it should be used sparingly (e.g., only when the bot's current path is blocked or a high-priority target appears).
-   **Latency Handling**: Because the AI is server-authoritative, it is not affected by network latency in the same way human players are. Its actions are executed immediately on the server. The results of these actions are then broadcast to clients as part of the normal state sync.
-   **Offline Mode**: For a single-player mode, the server logic (including the `GameInstance` and `AIBot` nodes) can be run directly on the client machine. The networking layer would be bypassed.

## 6. Testing and Evaluation

1.  **Debug Visualizations**: Create a debug mode that can be enabled on the server to visualize the AI's decisions. This could include drawing the danger map, the bot's chosen path, and the utility score of each tile.
2.  **Test Scenarios**:
    -   **Survival Test**: A map where bombs are dropped randomly, and the bot must survive as long as possible.
    -   **Trap Test**: A scenario with a stationary "dummy" player to see if the bot can successfully trap it.
    -   **Power-up Test**: A map filled with power-ups to ensure the bot prioritizes and collects them.
3.  **Metrics**:
    -   Average survival time.
    -   Number of opponents defeated.
    -   Number of self-inflicted deaths.
    -   Power-ups collected per match.
    -   APM (Actions Per Minute) to ensure the bot isn't too robotic.

## 7. Future Expansion

-   **Reinforcement Learning**: The utility function values (e.g., `+500` for a power-up) are currently hand-tuned. In the future, these weights could be learned via a reinforcement learning algorithm (like Q-learning) by having bots play against each other thousands of times.
-   **Player Mimicry**: The server could record human player data (e.g., common escape patterns, bomb placement strategies) and use it to train a model that mimics human playstyles.
-   **AI Personalities**: Create different "personalities" by having multiple sets of utility weights. For example:
    -   **AggressiveBot**: High utility for trapping opponents, low penalty for risk.
    -   **TimidBot**: Very high utility for safety, avoids opponents.
    -   **GreedyBot**: Prioritizes power-ups above all else.
