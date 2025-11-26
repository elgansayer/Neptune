#!/bin/bash
# Bot Suicide Validation Test
# Runs game multiple times and checks for suicides

RUNS=5
DURATION=60  # seconds per run
PROJECT_DIR="/home/elgan/bomberman"
RESULTS_FILE="$PROJECT_DIR/suicide_validation_results.txt"

echo "=========================================="
echo "BOT SUICIDE VALIDATION TEST"
echo "=========================================="
echo "Runs: $RUNS"
echo "Duration per run: $DURATION seconds"
echo "Results file: $RESULTS_FILE"
echo ""

# Clear results file
echo "Suicide Validation Test - $(date)" > "$RESULTS_FILE"
echo "========================================" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

TOTAL_SUICIDES=0
TOTAL_DEATHS=0
TOTAL_BOMBS=0

for i in $(seq 1 $RUNS); do
  echo "Run $i/$RUNS..."
  
  RUN_LOG="$PROJECT_DIR/run_${i}.log"
  
  # Run game
  timeout ${DURATION}s bash -c "cd $PROJECT_DIR && ./bomberman both 2>&1" > "$RUN_LOG" 2>&1 || true
  
  # Count events
  SUICIDES=$(grep -c "SUICIDE\|suicide\|died from own bomb" "$RUN_LOG" 2>/dev/null || echo "0")
  DEATHS=$(grep -c "died\|killed\|eliminated" "$RUN_LOG" 2>/dev/null || echo "0")
  BOMBS=$(grep -c "Placed bomb\|bomb placed" "$RUN_LOG" 2>/dev/null || echo "0")
  BOTS=$(grep "Spawned bot" "$RUN_LOG" | wc -l || echo "0")
  
  TOTAL_SUICIDES=$((TOTAL_SUICIDES + SUICIDES))
  TOTAL_DEATHS=$((TOTAL_DEATHS + DEATHS))
  TOTAL_BOMBS=$((TOTAL_BOMBS + BOMBS))
  
  echo "  Bots: $BOTS | Bombs: $BOMBS | Deaths: $DEATHS | Suicides: $SUICIDES"
  
  echo "Run $i: Bots=$BOTS Bombs=$BOMBS Deaths=$DEATHS Suicides=$SUICIDES" >> "$RESULTS_FILE"
  
  # Clean up
  rm -f "$RUN_LOG"
  
  sleep 1
done

echo "" >> "$RESULTS_FILE"
echo "========================================" >> "$RESULTS_FILE"
echo "TOTAL RESULTS" >> "$RESULTS_FILE"
echo "========================================" >> "$RESULTS_FILE"
echo "Total Suicides: $TOTAL_SUICIDES" >> "$RESULTS_FILE"
echo "Total Deaths: $TOTAL_DEATHS" >> "$RESULTS_FILE"
echo "Total Bombs: $TOTAL_BOMBS" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

if [ $TOTAL_SUICIDES -eq 0 ]; then
  echo "✅ SUCCESS: 0 suicides detected across $RUNS runs" >> "$RESULTS_FILE"
  echo "Status: PASS" >> "$RESULTS_FILE"
else
  echo "❌ FAILURE: $TOTAL_SUICIDES suicides detected" >> "$RESULTS_FILE"
  echo "Status: FAIL" >> "$RESULTS_FILE"
fi

echo ""
echo "=========================================="
echo "VALIDATION COMPLETE"
echo "=========================================="
cat "$RESULTS_FILE"
echo ""

if [ $TOTAL_SUICIDES -eq 0 ]; then
  echo "✅ All tests passed - No suicides detected"
  exit 0
else
  echo "❌ Tests failed - Suicides detected: $TOTAL_SUICIDES"
  exit 1
fi
