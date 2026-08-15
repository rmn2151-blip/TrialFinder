#!/usr/bin/env bash
#
# Start the TrialFinder backend for local development.
#
#   ./run.sh
#
# Why this script exists: `uvicorn --reload` watches the current directory,
# and `venv/` lives inside it. Any file pip or Python touches inside the venv
# triggers a restart, which kills in-flight requests and shows up in the app
# as "The request timed out". Here we watch only our own source folders.

set -euo pipefail

cd "$(dirname "$0")"

if [[ -d "venv" && -z "${VIRTUAL_ENV:-}" ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

# Free the port if a previous run is still holding it.
if lsof -ti:8000 >/dev/null 2>&1; then
  echo "Port 8000 is in use. Stopping the old server..."
  lsof -ti:8000 | xargs kill -9 2>/dev/null || true
  sleep 1
fi

echo "Starting TrialFinder API on http://localhost:8000"
echo "Watching: db, jobs, middleware, models, prompts, routers, services, main.py"
echo

exec python -m uvicorn main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --reload \
  --reload-dir db \
  --reload-dir jobs \
  --reload-dir middleware \
  --reload-dir models \
  --reload-dir prompts \
  --reload-dir routers \
  --reload-dir services \
  --reload-include 'main.py' \
  --reload-exclude 'venv/*' \
  --reload-exclude '*.db' \
  --reload-exclude '__pycache__/*'
