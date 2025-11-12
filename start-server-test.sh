#!/bin/bash
# Quick connection test

cd /home/elgan/bomberman

echo "Starting server in background..."
godot --headless --path server/ > /tmp/bomberman-server.log 2>&1 &
SERVER_PID=$!

echo "Server PID: $SERVER_PID"
echo "Waiting 3 seconds for server to start..."
sleep 3

echo ""
echo "Server output:"
head -20 /tmp/bomberman-server.log
echo ""

echo "Server is running. You can now:"
echo "  1. Run './bomberman client' in another terminal"
echo "  2. Or just open Godot and run the project"
echo ""
echo "To stop the server: kill $SERVER_PID"
echo "Server log: /tmp/bomberman-server.log"
