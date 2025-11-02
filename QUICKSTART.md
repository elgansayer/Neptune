# Bomberman - Quick Start Guide

## ✅ What's Been Done (Tasks 1-5)

### 1. ✅ Project Structure Created
- **client/**: Client-only code with UI and main_client.gd
- **server/**: Server-only code with auth, lobby, and main_server.gd  
- **shared/**: Code shared between client and server (constants, entities, game logic)

### 2. ✅ Authentication System
- Abstract `BackendService` interface for easy migration to PlayFab
- `LocalBackend` implementation (in-memory, no persistence yet)
- RPC-based login/register between client and server
- Ready for PlayFab/Nakama integration later

### 3. ✅ ENet Networking
- Server listens on port 7777
- Client connects via `ENetMultiplayerPeer`
- RPC authentication flow implemented
- Connection/disconnection handlers

### 4. ❌ Game Logic Port (NOT DONE YET)
This is the big task - porting the current Nakama-based game logic to server-authoritative Godot physics.

### 5. ✅ Cleanup Documented
See `CLEANUP.md` for detailed list of files to delete. **Awaiting your approval before deleting.**

## Testing the Current Setup

### Start Server
```bash
cd /home/elgan/bomberman/server
godot --headless --path . res://server/main_server.tscn
```

### Start Client (in separate terminal)
```bash
cd /home/elgan/bomberman
godot --path . res://client/ui/login_screen.tscn
```

Or just open the project in Godot editor - it will launch the login screen.

## What Works Now
- ✅ Server starts and listens on port 7777
- ✅ Client connects to server
- ✅ Registration (username/password stored in memory)
- ✅ Login authentication

## What Doesn't Work Yet
- ❌ No game logic - just auth for now
- ❌ No lobby system
- ❌ No server-side physics/collision
- ❌ Old Nakama-based game is broken (expected)

## Next Steps

### Option A: Quick Test
1. Open project in Godot
2. You'll see login screen
3. Click "Register", enter username/password
4. Click "Login" with same credentials
5. Should see "Login successful!" (but no game yet)

### Option B: Delete Old Files
Run the cleanup commands from `CLEANUP.md` to remove ~60MB of unused Nakama/test files.

### Option C: Port Game Logic (Big Task)
This is task #4 - requires:
- Creating server-side player CharacterBody2D
- Implementing bomb placement with collision exceptions
- Adding explosion logic
- State synchronization to clients
- Estimated: 3-4 hours of work

## Files Created

### Core
- `shared/constants.gd` - Game constants
- `shared/backend_service.gd` - Abstract backend interface
- `server/main_server.gd` - Server entry point
- `server/auth/local_backend.gd` - Local auth implementation
- `server/lobby/lobby_manager.gd` - Lobby manager (stub)
- `client/main_client.gd` - Client entry point
- `client/ui/login_screen.gd` - Login UI

### Config
- `server/project.godot` - Server project config
- `project.godot` - Updated to remove Nakama, use ClientMain autoload

### Docs
- `ARCHITECTURE.md` - Architecture overview
- `CLEANUP.md` - Files to delete
- This file!

## Important Notes

⚠️ **The old game is now broken** - This is expected! The old `GameManager.gd` uses Nakama, which we removed from autoload. Don't try to run the old scenes.

✅ **The new architecture is sound** - Client/server separation is clean, ready for game logic port.

🔮 **PlayFab migration is easy** - Just create `PlayFabBackend extends BackendService` and swap it in `main_server.gd`.

## Questions?

What would you like to do next:
1. Test the login flow?
2. Delete old files?
3. Start porting game logic (Task #4)?
