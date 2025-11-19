#!/bin/bash
# Test bot escape behavior

cd /home/elgan/bomberman
timeout 45s ./bomberman both 2>&1 | tee /tmp/bot_test.log &
GAME_PID=$!

sleep 5
echo "=== Checking for escape behavior ==="
grep -E "(BTFindEscapeRoute|escape_cell|avoid_threats)" /tmp/bot_test.log | tail -20

wait $GAME_PID
echo "=== Test complete ==="
