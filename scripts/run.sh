#!/usr/bin/env bash
# Launch LiteVNA Studio (macOS / Linux / Windows with Python).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  exec "${ROOT}/.venv/bin/python" -m litevna.app "$@"
fi
exec python3 -m litevna.app "$@"
