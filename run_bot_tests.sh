#!/bin/bash
# Bot Test Suite Runner
# Executes all bot tests and generates report

set -e

PROJECT_DIR="$(pwd)"
TEST_DIR="$PROJECT_DIR/tests"
LOG_FILE="$PROJECT_DIR/test_results.log"

echo "=========================================="
echo "BOMBERMAN BOT TEST SUITE"
echo "=========================================="
echo ""
echo "Starting time: $(date)"
echo "Log file: $LOG_FILE"
echo ""

# Clear previous log
echo "[TEST RUN STARTED: $(date)]" > "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Run survival tests
echo "Running SURVIVAL tests..."
timeout 120s godot --headless --path "$PROJECT_DIR" \
  --script "$TEST_DIR/bot_test_runner.gd" \
  >> "$LOG_FILE" 2>&1 || {
    echo "Test suite timed out or failed"
  }

# Extract results
echo ""
echo "=========================================="
echo "TEST RESULTS"
echo "=========================================="
grep -E "PASS|FAIL|BOT TEST SUMMARY" "$LOG_FILE" | tail -20

# Check for suicides
SUICIDES=$(grep -c "SUICIDE" "$LOG_FILE" || echo "0")
if [ "$SUICIDES" -gt 0 ]; then
  echo ""
  echo "⚠️  WARNING: $SUICIDES bot suicides detected!"
  echo ""
  echo "Suicide cases:"
  grep "SUICIDE" "$LOG_FILE"
fi

echo ""
echo "Full log available at: $LOG_FILE"
echo ""
