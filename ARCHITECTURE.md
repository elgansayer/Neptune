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
