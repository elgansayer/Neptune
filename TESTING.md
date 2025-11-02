# Testing the New Architecture

## What Works Now

### ✅ Server-Authoritative Physics
- Players use `CharacterBody2D` with `move_and_slide()`
- Bombs use `StaticBody2D` with collision shapes
- Collision exceptions work like old SBomberman project
- Player can walk out of bomb, then bomb becomes solid

### ✅ Networking
- ENet client-server communication
- RPC-based authentication
- RPC-based input handling
- State synchronization (20Hz)

### ✅ Game Logic
- Player movement with Godot physics
- Bomb placement with collision exceptions
- Bomb explosion with area damage
- Multi-directional explosion propagation

## How to Test

### 1. Start Server
```bash
cd /home/elgan/bomberman
godot --headless --path . res://server/main_server.tscn
```

Or use the CLI tool:
```bash
./bomberman server
```

You should see:
```
=== Bomberman Server Starting ===
[LocalBackend] In-memory auth initialized
Server listening on port 7777
```

### 2. Start Client
In a separate terminal:
```bash
cd /home/elgan/bomberman
godot --path .
```

Or use the CLI tool:
```bash
./bomberman client
```

**Or start both at once:**
```bash
./bomberman both
```

### 3. Register and Login
1. Enter username (3+ chars) and password (6+ chars)
2. Click "Register"
3. Click "Login" with same credentials
4. After ~0.5s, should switch to game view

### 4. Play!
- **Arrow keys**: Move player
- **Space**: Place bomb
- Walk out of bomb immediately after placing
- Bomb explodes after 3 seconds
- Explosion kills players in its path

### 5. Test Collision Exception System
1. Place bomb with Space
2. Walk away from bomb (any direction)
3. Try to walk back into bomb - should be blocked!
4. This confirms collision exception cleared properly

## Known Issues

- No visual sprites yet (using icon.svg placeholders)
- No map rendering (just empty space)
- No lobby system (auto-starts game)
- Only one player per game (no multiplayer yet)
- No respawn system
- No powerups
- Camera might be jittery

## Next Steps

1. Add proper player sprites and animations
2. Render the map tiles
3. Support multiple players in one game
4. Add lobby system for matchmaking
5. Client prediction for smoother movement
6. Add explosions visual effects
7. Add powerups (speed, bomb range, max bombs)

## Architecture Benefits

✅ **No more manual collision detection** - Godot handles it
✅ **Clean physics** - `move_and_slide()` just works
✅ **Easy bomb collision** - `add_collision_exception_with()` like old project
✅ **Server authoritative** - No cheating possible
✅ **Easy to add physics features** - Throwing/kicking bombs will be trivial (just `apply_impulse()`)
