# LimboAI Installation Instructions for Neptune-Bomberman

## Prerequisites

- Godot 4.4 or later
- Access to Godot Editor (not just CLI)
- Git (for cloning demo project)

## Installation Steps

### Option 1: Via Godot Asset Library (Recommended)

1. **Open Project in Godot Editor**
   ```bash
   godot --path /path/to/Neptune-Bomberman
   ```

2. **Access Asset Library**
   - Click the "AssetLib" tab at the top of the Godot Editor
   - Search for "LimboAI"
   - Click "Download"
   - Click "Install"

3. **Reload Project**
   - Go to `Project -> Reload Current Project`
   - This ensures the GDExtension is properly loaded

4. **Verify Installation**
   - Create a test scene
   - Add a new node → Search for "BTPlayer"
   - If BTPlayer node appears, installation was successful!

### Option 2: Manual Installation from GitHub

1. **Download Latest Release**
   - Visit: https://github.com/limbonaut/limboai/releases/latest
   - Download: `limboai-gdextension.v1.5.x.zip` (or latest version)

2. **Extract to Project**
   ```bash
   cd /path/to/Neptune-Bomberman
   unzip limboai-gdextension.v1.5.x.zip
   ```
   
   This should create:
   ```
   addons/limboai/
   ├── bin/
   │   ├── limboai.linux.debug.x86_64.so
   │   ├── limboai.linux.release.x86_64.so
   │   ├── limboai.windows.debug.x86_64.dll
   │   └── ...
   ├── icons/
   ├── limboai.gdextension
   └── plugin.cfg
   ```

3. **Enable Plugin**
   - Open project in Godot Editor
   - Go to `Project -> Project Settings -> Plugins`
   - Enable "LimboAI"

4. **Reload Project**
   - `Project -> Reload Current Project`

### Option 3: For Server-Only (Headless) Deployment

If you only need LimboAI for the headless server:

1. **Install on Development Machine First**
   - Follow Option 1 or 2 on your dev machine
   - Ensure the addon works in the editor

2. **Copy to Server Project**
   ```bash
   # From your main project
   cp -r addons/limboai /path/to/Neptune-Bomberman/server/addons/
   ```

3. **Update Server project.godot**
   ```ini
   [editor_plugins]
   enabled=PackedStringArray("res://addons/limboai/plugin.gd")
   ```

4. **Test Headless Server**
   ```bash
   cd server
   godot --headless --path . res://server/main_server.tscn
   ```

## Post-Installation Verification

### Test 1: Create a Simple BT

1. **Create New BehaviorTree Resource**
   - Right-click in FileSystem
   - New Resource → BehaviorTree
   - Save as `test_bt.tres`

2. **Open BT Editor**
   - Double-click the BehaviorTree resource
   - Bottom panel should show "LimboAI" tab with BT editor

3. **Add Some Nodes**
   - Right-click in editor → Add Task
   - Try adding: BTAction, BTCondition, BTSequence

### Test 2: Run Demo Project

1. **Get Demo Project**
   ```bash
   cd /tmp
   git clone --depth 1 https://github.com/limbonaut/limboai.git
   ```

2. **Open Demo in Godot**
   ```bash
   godot --path limboai/demo
   ```

3. **Run Showcase**
   - Run `demo/scenes/showcase.tscn`
   - Should see working AI enemies

### Test 3: Create Test BTPlayer Node

Create a test script:

```gdscript
# test_limboai.gd
extends Node

func _ready():
    var bt_player = BTPlayer.new()
    add_child(bt_player)
    
    var bt = BehaviorTree.new()
    bt_player.behavior_tree = bt
    
    if bt_player:
        print("✅ LimboAI successfully installed!")
        print("   BTPlayer: ", bt_player)
        print("   BehaviorTree: ", bt)
    else:
        print("❌ LimboAI installation failed")
```

Run this script and check the output.

## Troubleshooting

### Issue: "BTPlayer" node not found

**Solution**:
1. Ensure you've reloaded the project after installation
2. Check that `addons/limboai/limboai.gdextension` exists
3. Verify the plugin is enabled in Project Settings

### Issue: "Error loading GDExtension"

**Solution**:
1. Make sure you downloaded the correct version for your Godot version
2. Check that binary files exist in `addons/limboai/bin/`
3. Verify file permissions (Linux/Mac):
   ```bash
   chmod +x addons/limboai/bin/*.so
   ```

### Issue: Works in editor but not in exported game

**Solution**:
1. Ensure export settings include GDExtension libraries
2. In Export dialog → Resources → Enable "Export GDExtension"
3. Check that `addons/limboai/bin/` binaries are included

### Issue: Server (headless) crashes on startup

**Solution**:
1. Ensure headless server binaries are present:
   ```
   addons/limboai/bin/limboai.linux.release.x86_64.so
   ```
2. Check that GDExtension is compatible with headless mode
3. Try running with `--verbose` flag to see error messages

## Next Steps After Installation

Once LimboAI is successfully installed:

1. **Read the Refactoring Guide**
   - See `docs/LIMBOAI_REFACTOR_GUIDE.md`

2. **Explore Example Nodes**
   - Check `shared/ai/limbo_nodes/` for custom node examples

3. **Start with Phase 1**
   - Create a simple BT for bomb lifecycle
   - Test with a single entity before refactoring everything

4. **Use the Debugger**
   - Bottom panel → LimboAI tab → Debugger
   - Super useful for understanding BT execution

## Additional Resources

- **Official Documentation**: https://limboai.readthedocs.io/
- **GitHub Repository**: https://github.com/limbonaut/limboai
- **Discord Community**: https://discord.gg/N5MGC95GpP
- **Video Tutorials**: Search YouTube for "LimboAI Godot"

## Compatibility Matrix

| Godot Version | LimboAI Version | Notes |
|---------------|-----------------|-------|
| 4.4+          | 1.5.x          | ✅ Recommended |
| 4.3           | 1.2.0 - 1.3.x  | ⚠️ Older |
| 4.2           | 1.1.x          | ⚠️ Limited features |

## Docker/CI Setup

For automated testing in CI/CD:

```dockerfile
# Dockerfile for building with LimboAI
FROM barichello/godot-ci:4.4

# Install LimboAI
RUN mkdir -p /root/.local/share/godot/export_templates/4.4.stable
COPY addons/limboai /build/addons/limboai

# Export with GDExtension support
CMD godot --headless --export-release "Linux/X11" /build/output/game.x86_64
```

## License

LimboAI is licensed under MIT license. Make sure to include license attribution if distributing.

---

**Ready to start refactoring?**

Proceed to `docs/LIMBOAI_REFACTOR_GUIDE.md` for the complete migration plan!
