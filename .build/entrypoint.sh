#!/usr/bin/env bash
set -euo pipefail

INTERVAL=${INTERVAL_SECONDS:-300}
SCRIPT_ARGS=("$@")

echo "Container run arguments: ${SCRIPT_ARGS[*]}"
echo ""

# If the script was invoked with --auth-only, run once and exit after authentication
for _arg in "${SCRIPT_ARGS[@]:-}"; do
  if [ "${_arg}" = "--auth-only" ]; then
    echo "Auth-only mode detected: running once and exiting"
    exec python3 /app/sporganize.py "${SCRIPT_ARGS[@]}" || { echo "sporganize exited with error $?"; exit 1; }
  fi
done

if [ "$INTERVAL" = "0" ] || [ "${RUN_ONCE:-0}" = "1" ]; then
  echo "Running sporganize once"
  exec python3 /app/sporganize.py "${SCRIPT_ARGS[@]}" || { echo "sporganize exited with error $?"; exit 1; }
fi

while true; do
  echo "Running sporganize at $(date)"
  python3 /app/sporganize.py "${SCRIPT_ARGS[@]}" || { echo "sporganize exited with error $?"; exit 1; }
  sleep "$INTERVAL"
done
