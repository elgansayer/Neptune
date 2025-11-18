#!/usr/bin/env python3
"""
Bomberman Development CLI Tool
Manage server, client, and development tasks
"""

import argparse
import subprocess
import sys
import os
import signal
import time
from pathlib import Path

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.absolute()
SERVER_PATH = PROJECT_ROOT / "server"
CLIENT_PATH = PROJECT_ROOT

class Colors:
    """Terminal colors"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    """Print colored header"""
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}\n")

def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.END}", file=sys.stderr)

def print_info(text):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")

def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

def check_godot():
    """Check if Godot is available"""
    try:
        result = subprocess.run(['godot', '--version'], 
                              capture_output=True, 
                              text=True,
                              timeout=5)
        if result.returncode == 0:
            version = result.stdout.strip()
            print_success(f"Godot found: {version}")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    print_error("Godot not found in PATH")
    print_info("Install Godot or add it to your PATH")
    return False

def start_server(args):
    """Start the Bomberman server"""
    print_header("Starting Bomberman Server")
    
    if not check_godot():
        return 1
    
    print_info(f"Server path: {SERVER_PATH}")
    print_info("Starting headless server on port 7777...")
    print_info("Press Ctrl+C to stop\n")
    
    try:
        cmd = [
            'godot',
            '--headless',
            '--path', str(SERVER_PATH),  # Run from server directory
            '--', '--server'  # Pass server argument
        ]
        
        if args.verbose:
            print_info(f"Command: {' '.join(cmd)}\n")
        
        process = subprocess.Popen(cmd)
        process.wait()
        
    except KeyboardInterrupt:
        print_info("\nShutting down server...")
        process.terminate()
        process.wait(timeout=5)
        print_success("Server stopped")
    except Exception as e:
        print_error(f"Failed to start server: {e}")
        return 1
    
    return 0

def start_client(args):
    """Start the Bomberman client"""
    print_header("Starting Bomberman Client")
    
    if not check_godot():
        return 1
    
    print_info(f"Client path: {CLIENT_PATH}")
    print_info("Launching client...\n")
    
    try:
        cmd = ['godot', '--path', str(CLIENT_PATH)]
        
        if args.scene:
            cmd.extend(['res://' + args.scene])
        
        if args.verbose:
            print_info(f"Command: {' '.join(cmd)}\n")
        
        subprocess.run(cmd)
        
    except KeyboardInterrupt:
        print_info("\nClient closed")
    except Exception as e:
        print_error(f"Failed to start client: {e}")
        return 1
    
    return 0

def start_both(args):
    """Start both server and client"""
    print_header("Starting Server & Client")
    
    if not check_godot():
        return 1
    
    print_info("Starting server in background...")
    
    try:
        # Start server in background (always show output for debugging)
        server_cmd = [
            'godot',
            '--headless',
            '--path', str(SERVER_PATH),
            '--',
            '--server'
        ]
        
        # Create log file for server output
        server_log = PROJECT_ROOT / 'server.log'
        log_file = open(server_log, 'w')
        
        server_process = subprocess.Popen(
            server_cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT
        )
        
        print_success("Server started (PID: {})".format(server_process.pid))
        print_info(f"Server log: {server_log}")
        print_info("Waiting 2 seconds for server to initialize...")
        time.sleep(2)
        
        # Start client with logging
        print_info("Launching client...\n")
        client_cmd = ['godot', '--path', str(CLIENT_PATH)]
        
        if args.scene:
            client_cmd.extend(['res://' + args.scene])
        
        # Create log file for client output
        client_log = PROJECT_ROOT / 'client.log'
        client_log_file = open(client_log, 'w')
        
        subprocess.run(client_cmd, stdout=client_log_file, stderr=subprocess.STDOUT)
        
        print_info("\nClient closed. Stopping server...")
        client_log_file.close()
        log_file.close()
        server_process.terminate()
        server_process.wait(timeout=5)
        print_success("Server stopped")
        print_info(f"Server log saved to: {server_log}")
        print_info(f"Client log saved to: {client_log}")
        
    except KeyboardInterrupt:
        print_info("\nShutting down...")
        if server_process:
            log_file.close()
            server_process.terminate()
            server_process.wait(timeout=5)
        print_success("Stopped")
    except Exception as e:
        print_error(f"Failed: {e}")
        if server_process:
            if log_file:
                log_file.close()
            server_process.terminate()
        return 1
    
    return 0

def run_tests(args):
    """Run test suite"""
    print_header("Running Tests")
    
    test_path = PROJECT_ROOT / "test_suite"
    if not test_path.exists():
        print_error("Test suite not found")
        return 1
    
    print_info(f"Test path: {test_path}")
    print_info("Running tests...\n")
    
    try:
        cmd = [
            'godot',
            '--headless',
            '--path', str(test_path),
            'res://runner.tscn'
        ]
        
        if args.verbose:
            print_info(f"Command: {' '.join(cmd)}\n")
        
        result = subprocess.run(cmd)
        
        if result.returncode == 0:
            print_success("\nAll tests passed!")
        else:
            print_error("\nTests failed!")
        
        return result.returncode
        
    except Exception as e:
        print_error(f"Failed to run tests: {e}")
        return 1

def show_status(args):
    """Show project status"""
    print_header("Bomberman Project Status")
    
    # Check Godot
    print(f"{Colors.BOLD}Godot Engine:{Colors.END}")
    check_godot()
    print()
    
    # Check paths
    print(f"{Colors.BOLD}Project Paths:{Colors.END}")
    paths = {
        "Project Root": PROJECT_ROOT,
        "Server": SERVER_PATH,
        "Client": CLIENT_PATH,
        "Shared": PROJECT_ROOT / "shared",
    }
    
    for name, path in paths.items():
        exists = "✓" if path.exists() else "✗"
        color = Colors.GREEN if path.exists() else Colors.RED
        print(f"  {color}{exists}{Colors.END} {name}: {path}")
    print()
    
    # Check key files
    print(f"{Colors.BOLD}Key Files:{Colors.END}")
    key_files = [
        "server/main_server.gd",
        "server/game_instance.gd",
        "client/main_client.gd",
        "client/game_view.gd",
        "shared/constants.gd",
        "shared/entities/server_player.gd",
        "shared/entities/server_bomb.gd",
    ]
    
    for file in key_files:
        path = PROJECT_ROOT / file
        exists = "✓" if path.exists() else "✗"
        color = Colors.GREEN if path.exists() else Colors.RED
        print(f"  {color}{exists}{Colors.END} {file}")
    print()
    
    # Project info
    print(f"{Colors.BOLD}Documentation:{Colors.END}")
    docs = ["README.md", "PLAN.md", "ARCHITECTURE.md", "TESTING.md"]
    for doc in docs:
        path = PROJECT_ROOT / doc
        if path.exists():
            print(f"  {Colors.GREEN}✓{Colors.END} {doc}")
    
    return 0

def clean_project(args):
    """Clean generated files"""
    print_header("Cleaning Project")
    
    patterns = [
        ".godot/",
        "*.import",
        ".mono/",
        "bin/",
        "__pycache__/",
    ]
    
    print_info("Cleaning patterns: " + ", ".join(patterns))
    
    if not args.force:
        response = input(f"\n{Colors.YELLOW}This will delete generated files. Continue? (y/N): {Colors.END}")
        if response.lower() != 'y':
            print_info("Cancelled")
            return 0
    
    print_info("Cleaning...")
    
    # This is a placeholder - implement actual cleaning logic
    print_warning("Clean functionality not fully implemented yet")
    print_info("Manually delete .godot folders if needed")
    
    return 0

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Bomberman Development CLI Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s server              Start the server
  %(prog)s client              Start the client
  %(prog)s both                Start both server and client
  %(prog)s status              Show project status
  %(prog)s test                Run tests
        """
    )
    
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='verbose output')
    
    subparsers = parser.add_subparsers(dest='command', help='command to run')
    
    # Server command
    server_parser = subparsers.add_parser('server', help='start the server')
    server_parser.set_defaults(func=start_server)
    
    # Client command
    client_parser = subparsers.add_parser('client', help='start the client')
    client_parser.add_argument('--scene', help='specific scene to load')
    client_parser.set_defaults(func=start_client)
    
    # Both command
    both_parser = subparsers.add_parser('both', help='start server and client')
    both_parser.add_argument('--scene', help='specific scene to load')
    both_parser.set_defaults(func=start_both)
    
    # Test command
    test_parser = subparsers.add_parser('test', help='run tests')
    test_parser.set_defaults(func=run_tests)
    
    # Status command
    status_parser = subparsers.add_parser('status', help='show project status')
    status_parser.set_defaults(func=show_status)
    
    # Clean command
    clean_parser = subparsers.add_parser('clean', help='clean generated files')
    clean_parser.add_argument('-f', '--force', action='store_true',
                            help='skip confirmation')
    clean_parser.set_defaults(func=clean_project)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print_info("\nInterrupted")
        return 130

if __name__ == '__main__':
    sys.exit(main())
