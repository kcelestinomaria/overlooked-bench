#!/usr/bin/env bash
# overlooked-bench - one command to run the whole pipeline.
#
#   ./run.sh                      # full run, today's date as the run id
#   ./run.sh --run-id 2026-10-01  # ...or a specific run id
#   ./run.sh doctor               # check environment before a long run
#
# Any argument that is not a known subcommand is passed through to `obench.py run`.
set -euo pipefail
cd "$(dirname "$0")"

if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
elif [ -x ".venv/Scripts/python.exe" ]; then
  PY=".venv/Scripts/python.exe"
else
  echo "No virtualenv found. Create one first:"
  echo "  python -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

case "${1:-run}" in
  run|eval|charts|social|readme|site|validate|doctor) exec "$PY" obench.py "$@" ;;
  *) exec "$PY" obench.py run "$@" ;;
esac
