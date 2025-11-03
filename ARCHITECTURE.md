# Bomberman Server + Client Architecture

## Project Structure

This project has been refactored into a client/server architecture:

```
bomberman/
├── client/              # Client-only code
│   ├── ui/              # Login, lobby, HUD
│   ├── prediction/      # Client prediction (future)
│   └── main_client.gd   # Client entry point
│
├── server/              # Server-only code  
│   ├── auth/            # Authentication (LocalBackend)
│   ├── lobby/           # Lobby/matchmaking
│   ├── database/        # Future: SQLite wrapper
│   ├── project.godot    # Headless server config
│   └── main_server.gd   # Server entry point
│
└── shared/              # Code used by both
    ├── entities/        # Player, Bomb, Powerup scenes
    ├── game_logic/      # Core game rules
    ├── maps/            # Map data
    ├── constants.gd     # Game constants
    └── backend_service.gd  # Abstract backend interface
```

## Running the Project

### Server (Headless)
```bash
cd server
godot --headless --path . res://server/main_server.tscn
```

### Client
```bash
godot --path . res://client/ui/login_screen.tscn
```

Or just open the main project in Godot editor (runs client by default).

## Authentication

Currently uses simple in-memory authentication (TODO: Add SQLite).
- Username/password required
- No encryption yet (dev only!)
- Abstract interface ready for PlayFab migration

## TODO

- [ ] Install GodotSQLite addon for persistent auth
- [ ] Implement server-side game physics
- [ ] Add lobby system
- [ ] Client prediction and reconciliation
- [ ] Migrate to PlayFab for production

## Network Protocol

- Client connects via ENet on port 7777
- RPC-based authentication
- Server-authoritative game logic
- Future: State snapshots + client prediction



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