# Bomberman CLI Tool

A command-line tool to manage the Bomberman development workflow.

## Installation

The CLI tool is already set up at the project root:
```bash
cd /home/elgan/bomberman
./bomberman --help
```

## Commands

### Server Management

**Start server:**
```bash
./bomberman server
```
Starts the headless Godot server on port 7777. Press Ctrl+C to stop.

**Start client:**
```bash
./bomberman client
```
Launches the Godot client.

**Start both:**
```bash
./bomberman both
```
Starts the server in the background, then launches the client. When you close the client, the server stops automatically.

### Development

**Show project status:**
```bash
./bomberman status
```
Displays:
- Godot installation check
- Project paths
- Key file existence
- Documentation files

**Run tests:**
```bash
./bomberman test
```
Runs the test suite (when available).

**Clean project:**
```bash
./bomberman clean
```
Removes generated files (.godot folders, etc). Use `-f` to skip confirmation.

## Options

**Verbose output:**
```bash
./bomberman -v server
./bomberman --verbose both
```
Shows detailed command information.

**Load specific scene:**
```bash
./bomberman client --scene client/ui/login_screen.tscn
./bomberman both --scene client/game_view.tscn
```

## Examples

### Quick Development Workflow
```bash
# Check project status
./bomberman status

# Start both server and client
./bomberman both

# Or start separately in different terminals:
# Terminal 1:
./bomberman server

# Terminal 2:
./bomberman client
```

### Testing
```bash
# Run all tests
./bomberman test

# Run with verbose output
./bomberman -v test
```

### Cleanup
```bash
# Clean with confirmation
./bomberman clean

# Clean without confirmation
./bomberman clean -f
```

## Requirements

- Python 3.6+
- Godot 4.5+ in PATH

If Godot is not in your PATH, you can:
1. Add it to PATH permanently in your shell config
2. Create an alias: `alias godot="/path/to/godot"`
3. Or modify the CLI script to use absolute path

## Troubleshooting

**"Godot not found in PATH"**
- Install Godot: https://godotengine.org/download
- Add to PATH or create symlink:
  ```bash
  sudo ln -s /path/to/godot /usr/local/bin/godot
  ```

**Permission denied**
```bash
chmod +x bomberman-cli.py
```

**Python not found**
- Install Python 3: `sudo apt install python3`

## Adding to System PATH

To use `bomberman` from anywhere:
```bash
# Add to ~/.bashrc or ~/.zshrc:
export PATH="$PATH:/home/elgan/bomberman"

# Or create system-wide symlink:
sudo ln -s /home/elgan/bomberman/bomberman /usr/local/bin/bomberman
```

Then you can run from anywhere:
```bash
bomberman status
bomberman both
```
