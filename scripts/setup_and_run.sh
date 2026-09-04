#!/usr/bin/env bash
# One-shot setup + launch for macOS / Linux.
# Usage: from anywhere → bash path/to/LiteVNA/scripts/setup_and_run.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f "$ROOT/requirements.txt" ]]; then
  echo "ERROR: requirements.txt not found in $ROOT"
  echo "Clone the repo first, e.g.:"
  echo "  git clone https://github.com/mhalaba/LiteVNA.git && cd LiteVNA"
  exit 1
fi

echo "==> Project: $ROOT"

if [[ ! -d .venv ]]; then
  echo "==> Creating .venv"
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
pip install -e .

echo "==> Starting LiteVNA Studio"
exec python -m litevna.app "$@"
