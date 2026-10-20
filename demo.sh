#!/usr/bin/env bash
# One-command demo: regenerate samples, inspect one plate, run the benchmark and the tests.
set -euo pipefail
cd "$(dirname "$0")"

# On this host `python3` in PATH is a user-local shim without numpy; the interpreter
# with OpenCV/numpy is /usr/bin/python3. Override with PYTHON=... if yours differs.
PYTHON="${PYTHON:-/usr/bin/python3}"

echo "== synth =="
"$PYTHON" -m fieldlens synth --out samples --n 8 --seed 7400

echo
echo "== inspect =="
"$PYTHON" -m fieldlens inspect samples/images/plate_0003_seed7403.png --out-dir out

echo
echo "== benchmark (acceptance gate F1 >= 0.80) =="
"$PYTHON" -m fieldlens benchmark --n 40

echo
echo "== tests =="
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 "$PYTHON" -m pytest tests
