# Neptune Bomberman

> **October 2026 restart:** start with [the current plan](docs/restart/README.md),
> [requirements](docs/restart/REQUIREMENTS.md), [online bots](docs/restart/BOTS.md)
> and [server handoff](docs/restart/SERVER_HANDOFF.md). The historical description
> below includes outdated paths/status claims. Verify them against the current code.

A competitive multiplayer Bomberman game with server-authoritative physics and modern networking.

## 🏗️ Architecture

- **Server**: Pure Godot headless server with native physics engine
- **Client**: Godot client for rendering and input
- **Backend**: Abstract interface ready for PlayFab integration
- **Physics**: Native Godot CharacterBody2D/StaticBody2D with collision exceptions

## 🚀 Quick Start

### Start Server
```bash
cd server
godot --headless --path . res://server/main_server.tscn
```

### Start Client
```bash
godot --path .
```

The client will auto-generate a random username (e.g., "Player_1234") and connect to localhost automatically.

## 🎮 Controls

- **Arrow Keys**: Move player
- **Space**: Place bomb

## 📁 Project Structure

```
bomberman/
├── client/              # Client-only code
│   ├── ui/              # Login, lobby, HUD
│   └── game_view.gd     # Game rendering
├── server/              # Server-only code
│   ├── auth/            # Authentication (temporary)
│   ├── lobby/           # Lobby system
│   └── game_instance.gd # Game logic
└── shared/              # Shared code
    ├── entities/        # Player, Bomb entities
    ├── constants.gd     # Game constants
    └── backend_service.gd  # Backend interface
```

## 📚 Documentation

- **`PLAN.md`** - Development roadmap and feature list
- **`ARCHITECTURE.md`** - System design overview
- **`TESTING.md`** - Testing guide and what works
- **`docs/SBOMBERMAN_REFERENCE.md`** - Reference implementation notes

## 📖 Reference: SBomberman

This project uses `SBomberman/` (located in the project root) as a **reference** for game mechanics. It's a previous client-authoritative peer-to-peer implementation.

**What to use from SBomberman:**
- Movement feel and game mechanics
- Bomb placement patterns
- Explosion logic
- Corner assistance/wall sliding

**What NOT to copy:**
- Networking architecture (it's peer-to-peer, we're client-server)
- State management patterns
- Trust model assumptions

See `docs/SBOMBERMAN_REFERENCE.md` for detailed comparison.

## ⚡ Current Status

### ✅ Working
- Server-authoritative physics with Godot engine
- Player movement with `CharacterBody2D` and `move_and_slide()`
- Bomb placement with collision exceptions
- Bomb explosions with multi-directional propagation
- Player death on explosion hit
- Basic networking (ENet client-server)
- State synchronization (20Hz)

### 🚧 In Progress
- Visual polish (sprites, animations)
- Multiple players per game
- Map rendering
- Lobby system

### 🔮 Planned Features
- Client-side prediction with server reconciliation
- Power-ups (speed, bomb range, max bombs)
- Destructible blocks with power-up drops
- PlayFab integration (accounts, matchmaking, leaderboards)
- Advanced bomb mechanics (throwing, kicking)
- Multiple game modes
- 10-player support
- Spectator mode

## 🛠️ Tech Stack

- **Engine**: Godot 4.5
- **Language**: GDScript
- **Networking**: ENet (client-server RPC)
- **Database**: SQLite (local), PlayFab (future)
- **Physics**: Native Godot physics engine

## 🎯 Why This Architecture?

**Previous attempts used Nakama TypeScript server** with manual collision detection. This required implementing physics from scratch and made complex features (throwing bombs, bouncing) very difficult.

**Current approach uses pure Godot server** with built-in physics:
- Native `move_and_slide()` and collision system
- Easy collision exceptions (`add_collision_exception_with()`)
- Trivial to add `apply_impulse()` for throwing mechanics
- PlayFab handles only meta-game features (not physics)

## 🤝 Contributing

See `PLAN.md` for the roadmap and upcoming features.

## 📝 License

See LICENSE file.
