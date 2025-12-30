#!/bin/bash
# Quick egg visibility test

echo "Starting egg visibility test..."
echo "" > server.log
echo "" > client.log

# Run for 15 seconds
timeout 15s ./bomberman both >/dev/null 2>&1

# Check results
echo "=== EGG Z-INDEX CHECK ==="
grep "z_index=" client.log | grep -i egg | tail -5

echo ""
echo "=== EGG SPRITE DETAILS ==="
grep "Egg sprite DETAIL" client.log | tail -3

echo ""
echo "=== EGG FINAL STATE ==="
grep "Egg node FINAL" client.log | tail -3

echo ""
echo "=== SERVER EGG SPAWNS ==="
grep "Spawned Tirra egg" server.log | head -5

echo ""
echo "Test complete!"
