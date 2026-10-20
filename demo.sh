#!/usr/bin/env bash
# One-command demo: regenerate samples, inspect one plate, run the benchmark and the tests.
set -euo pipefail
cd "$(dirname "$0")"

# Both `python3` and `/usr/bin/python3` on the evidence host carry OpenCV 5.
# Override with PYTHON=... if your default interpreter lacks the requirements.
PYTHON="${PYTHON:-python3}"

echo "== synth =="
"$PYTHON" -m fieldlens synth --out samples --n 8 --seed 7400

echo
echo "== inspect =="
"$PYTHON" -m fieldlens inspect samples/images/plate_0003_seed7403.png --out-dir out

echo
echo "== benchmark (three matchers, six-seed sweep) =="
"$PYTHON" -m fieldlens benchmark --n 40

echo
echo "== tests =="
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 "$PYTHON" -m pytest tests
