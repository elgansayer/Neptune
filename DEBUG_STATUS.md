# Bomberman Debug Status

## Current Situation
Server starts successfully and listens on port 7777, but there are cascading RPC configuration mismatches preventing gameplay.

## Fixed Issues ✅
1. ✅ MapGenerator preload added to map_manager.gd
2. ✅ MapLoader preload added to map_manager.gd  
3. ✅ receive_game_state → receive_state RPC naming fixed
4. ✅ spawn_ai_bot RPC removed (was causing ID collisions)
5. ✅ GameInstance compiles cleanly (AIPlayer disabled)
6. ✅ Server starts on port 7777
7. ✅ Duplicate server initialization fixed (_initialized flag)

## Current Blocker 🔴
**RPC ID Mismatch**: Client and server RPC configurations don't match

### Error
```
ERROR: Condition "!cache_config.configs.has(p_rpc_method_id)" is true.
   at: _process_rpc (modules/multiplayer/scene_rpc_interface.cpp:232)
```

### Root Cause
The RPC methods on client and server must be declared in **identical order** with **identical signatures**. Currently:

**Client Side** (`client/main_client.gd`):
- @rpc authenticate_request
- @rpc register_request  
- @rpc send_player_input
- @rpc request_join_game

**Server Side** (`server/main_server.gd`):
- @rpc register_user
- @rpc authenticate_request
- @rpc send_player_input
- @rpc request_join_game

❌ **ORDER MISMATCH**: Server has `register_user` first, client has `authenticate_request` first

### Solution Options

#### Option 1: Reorder RPCs to Match (Recommended)
Ensure BOTH client and server declare RPCs in the same order. Since the stub system doesn't work well, we should:

1. Remove stub autoloads entirely
2. Declare RPCs directly in both projects
3. Use same order and signatures

#### Option 2: Use RPC Names Instead of IDs
Configure Godot to use RPC names instead of numeric IDs (less efficient but more flexible):
```gdscript
MultiplayerAPI.rpc_mode = MultiplayerAPI.RPC_MODE_SYNC
```

#### Option 3: Shared RPC Interface
Create a shared script that both projects import, ensuring identical declarations.

## Files Requiring Attention
- `client/main_client.gd` - Client RPC declarations
- `server/main_server.gd` - Server RPC declarations
- `shared/client_stub.gd` - Currently in client project (may be causing issues)
- `shared/server_stub.gd` - Currently in server project
- `server/shared/client_stub.gd` - Duplicate copy in server
- `server/shared/server_stub.gd` - Duplicate copy in client

## Temporary Workarounds Applied
- AIPlayer completely disabled (prevents GameInstance compilation errors)
- spawn_ai_bot RPC removed (was causing Dictionary→int conversion errors)
- AI auto-spawning disabled in main_server.gd

## Testing Commands
```bash
# Test server only
./bomberman-cli.py server

# Test client only (in separate terminal)
./bomberman-cli.py client

# Test both together  
./bomberman-cli.py both

# Clean all caches
pkill -9 -f godot && rm -rf .godot server/.godot server.log
```

## Next Steps
1. Fix RPC method order mismatch
2. Verify client can authenticate
3. Test game instance creation
4. Re-enable AIPlayer once core gameplay works
5. Test power-up system
