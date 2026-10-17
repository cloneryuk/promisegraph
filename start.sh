#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
test -d .venv || python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
test -f .env || cp .env.example .env
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
