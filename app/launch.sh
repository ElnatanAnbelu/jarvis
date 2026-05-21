#!/bin/bash
# JARVIS App launcher — activates venv and starts the pywebview app
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"
exec "$DIR/venv/bin/python3" "$DIR/app/main.py" "$@"
