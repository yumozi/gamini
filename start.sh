#!/usr/bin/env bash
cd "$(dirname "$0")"

if [ -f .venv/Scripts/activate ]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi

python -m backend.main
