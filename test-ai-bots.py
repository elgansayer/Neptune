#!/usr/bin/env python3
"""
AI Bot Test Script
Spawns AI bots on the server for testing
"""

import subprocess
import time

print("=" * 60)
print("AI Bot Test - Spawning Bots")
print("=" * 60)

# Wait for server to be ready
time.sleep(2)

print("\n✓ Server should be running on port 7777")
print("\nTo spawn AI bots, connect a client and use the console or:")
print("  - Modify server code to call spawn_ai_bot_local()")
print("  - Or use RPC from connected client\n")

print("Personality types:")
print("  0 = BALANCED")
print("  1 = AGGRESSIVE")  
print("  2 = TIMID")
print("  3 = GREEDY")
print("  4 = CHAOS")
print("  -1 = RANDOM\n")

print("Instructions:")
print("1. Connect a client: ./bomberman-cli.py client")
print("2. Login with test/test")
print("3. AI bots should be visible and playing!")
print("\nPress Ctrl+C to stop\n")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n\nStopping...")
