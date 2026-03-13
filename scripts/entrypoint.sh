#!/usr/bin/env sh
set -eu

python /app/scripts/wait_for_napcat.py
exec uv run main.py
