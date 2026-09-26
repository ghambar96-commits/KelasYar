#!/usr/bin/env bash
# KelasYar launcher for Linux / macOS
set -e
cd "$(dirname "$0")"

PYTHON=${PYTHON:-python3}

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "[ERROR] python3 not found. Install Python 3.11+ first."
    exit 1
fi

if [ ! -d .venv ]; then
    echo "[1/3] Creating virtual environment..."
    "$PYTHON" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "[2/3] Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "[3/3] Starting KelasYar..."
echo "  web panel : http://localhost:8000/admin"
echo "  API docs  : http://localhost:8000/docs"
python run.py
