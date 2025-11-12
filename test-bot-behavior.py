#!/usr/bin/env python3
"""
Live AI Bot Behavior Test
Spawns server with AI bots and monitors bomb placement in real-time
"""

import subprocess
import sys
import time
import signal
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.absolute()

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.CYAN}ℹ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

print_header("Live AI Bot Behavior Test")

print_info("This test will:")
print("  1. Start headless server with AI bots")
print("  2. Monitor logs for bomb placement and movement")
print("  3. Report statistics after 60 seconds")
print("  4. Automatically stop\n")

# Start server
print_info("Starting server with AI bots...")
server_cmd = [
    'godot',
    '--headless',
    '--path', str(PROJECT_ROOT / 'server'),
    '--', '--server'
]

log_file_path = PROJECT_ROOT / 'bot_test.log'
log_file = open(log_file_path, 'w')

try:
    server_process = subprocess.Popen(
        server_cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=PROJECT_ROOT
    )
    
    print_success(f"Server started (PID: {server_process.pid})")
    print_info(f"Logging to: {log_file_path}")
    print_info("Waiting 5 seconds for server initialization...")
    time.sleep(5)
    
    # Monitor for 60 seconds
    print_info("Monitoring bot behavior for 60 seconds...")
    print(f"{Colors.YELLOW}  (You can Ctrl+C to stop early){Colors.END}\n")
    
    start_time = time.time()
    last_check = start_time
    check_interval = 10  # Check every 10 seconds
    
    stats = {
        'bombs_placed': 0,
        'blocks_destroyed': 0,
        'escapes_committed': 0,
        'bots_killed': 0,
        'safety_checks': 0,
        'safe_bombs': 0,
        'unsafe_bombs': 0
    }
    
    while time.time() - start_time < 60:
        time.sleep(1)
        
        # Read and analyze log every 10 seconds
        if time.time() - last_check >= check_interval:
            last_check = time.time()
            log_file.flush()
            
            with open(log_file_path, 'r') as f:
                content = f.read()
                
            # Count events
            stats['bombs_placed'] = content.count('[Game] Bomb placed')
            stats['blocks_destroyed'] = content.count('[Game] Destroying block')
            stats['escapes_committed'] = content.count('committing escape dir')
            stats['bots_killed'] = content.count('killed by explosion')
            stats['safety_checks'] = content.count('[AI-WANDER-BOMB] Checking safety')
            stats['safe_bombs'] = content.count('SAFE to bomb')
            stats['unsafe_bombs'] = content.count('No escape routes')
            
            elapsed = int(time.time() - start_time)
            print(f"\n{Colors.BOLD}[{elapsed}s] Current Statistics:{Colors.END}")
            print(f"  Bombs placed: {Colors.GREEN}{stats['bombs_placed']}{Colors.END}")
            print(f"  Blocks destroyed: {Colors.GREEN}{stats['blocks_destroyed']}{Colors.END}")
            print(f"  Escape commitments: {Colors.GREEN}{stats['escapes_committed']}{Colors.END}")
            print(f"  Bots killed: {Colors.YELLOW}{stats['bots_killed']}{Colors.END}")
            print(f"  Safety checks: {stats['safety_checks']} (Safe: {stats['safe_bombs']}, Unsafe: {stats['unsafe_bombs']})")
    
    # Final report
    print_header("Final Results")
    
    if stats['bombs_placed'] > 0:
        print_success(f"Bombs placed: {stats['bombs_placed']}")
        print_success(f"Blocks destroyed: {stats['blocks_destroyed']}")
        print_success(f"Escape commitments: {stats['escapes_committed']}")
        
        if stats['escapes_committed'] == stats['bombs_placed']:
            print_success("✓ All bombs triggered escape commitment!")
        else:
            print_warning(f"⚠ {stats['bombs_placed'] - stats['escapes_committed']} bombs didn't trigger escape")
        
        survival_rate = ((stats['bombs_placed'] - stats['bots_killed']) / stats['bombs_placed']) * 100
        print(f"\n  Bot survival rate: {survival_rate:.1f}%")
        print(f"  Safety check success rate: {(stats['safe_bombs']/(stats['safety_checks'] or 1)*100):.1f}%")
    else:
        print_warning("⚠ No bombs were placed!")
        print_info("  This suggests the AI is still not triggering bomb placement.")
        print_info("  Check bot_test.log for details.")
    
    print(f"\n{Colors.CYAN}Full log saved to: {log_file_path}{Colors.END}")

except KeyboardInterrupt:
    print_info("\n\nStopping early...")
except Exception as e:
    print(f"{Colors.RED}Error: {e}{Colors.END}")
finally:
    # Cleanup
    if 'server_process' in locals():
        print_info("Stopping server...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()
    
    if 'log_file' in locals():
        log_file.close()
    
    print_success("Test complete!\n")
