#!/usr/bin/env sh
# Algaroshy Farm launcher (macOS / Linux).  ./run.sh  |  ./run.sh demo  |  ./run.sh reset (clear history first)
cd "$(dirname "$0")" || exit 1
command -v node >/dev/null 2>&1 || { echo "Node.js 20+ is required: https://nodejs.org"; exit 1; }
exec node scripts/start.mjs "$@"
