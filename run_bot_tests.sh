#!/usr/bin/env bash
# Preserve the supervisor exit status, including runtime errors and timeouts.
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$PROJECT_DIR/tools/godot/run_bot_tests.py" "$@"
