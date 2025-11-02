# Files to Delete - Cleanup Plan

## Nakama-Related Files (No longer needed)
```
addons/com.heroiclabs.nakama/         # Entire Nakama addon
scripts/nakama/                        # Nakama client scripts
nakama_server/                         # Nakama server files
nakama_source/                         # Nakama source code
nakama-ctl                            # Nakama control script
scripts/Main.gd                       # Old Nakama-based main script
Main.tscn                             # Old Nakama-based main scene
```

## Old Test/Reference Projects
```
SBomberman/                           # Reference project (already analyzed)
test_suite/                           # Old test framework
codegen/                              # Code generation (unclear purpose)
nanobanana-output/                    # Generated output (unclear purpose)
```

## Unused/Duplicate Files
```
Game.tscn                             # Old game scene
scripts/GameManager.gd                # Old Nakama-based game manager
scripts/CharacterSelect.gd            # Old character select (Nakama-based)
scripts/TestSingleton.gd              # Test singleton
PLAN.md                               # Old plan document
prompt.md                             # Old prompts
firebase-debug.log                    # Firebase log (not using Firebase)
```

## Files to Keep and Move
```
characters/ → shared/entities/        # Player scenes
effects/ → shared/entities/           # Explosion effects  
res/tiles/ → shared/maps/             # Tile assets
art/ → shared/art/                    # Art assets
fonts/ → shared/art/fonts/            # Font assets
themes/ → client/ui/themes/           # UI themes
```

## Cleanup Actions

### 1. Delete Nakama files
```bash
rm -rf addons/com.heroiclabs.nakama
rm -rf scripts/nakama
rm -rf nakama_server
rm -rf nakama_source
rm nakama-ctl
```

### 2. Delete old test/reference projects
```bash
rm -rf SBomberman
rm -rf test_suite
rm -rf codegen
rm -rf nanobanana-output
```

### 3. Delete old/unused scripts and scenes
```bash
rm scripts/Main.gd
rm Main.tscn
rm Game.tscn
rm scripts/GameManager.gd
rm scripts/CharacterSelect.gd
rm scripts/TestSingleton.gd
rm PLAN.md
rm prompt.md
rm firebase-debug.log
```

### 4. Move shared assets (manual in Godot editor)
- Move `characters/` content to `shared/entities/`
- Move `effects/` content to `shared/entities/`
- Move `res/tiles/` to `shared/maps/tiles/`
- Move `art/` to `shared/art/`
- Move `themes/` to `client/ui/themes/`

## Estimated Space Savings
- Nakama source: ~50MB
- SBomberman reference: ~10MB  
- Total: ~60-70MB reduction
