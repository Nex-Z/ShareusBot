#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
PROJECT_NAME="${PROJECT_NAME:-shareusbot}"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "docker compose is required but not found." >&2
  exit 1
fi

run_compose() {
  "${COMPOSE_CMD[@]}" -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" "$@"
}

ensure_files() {
  if [[ ! -f .env ]]; then
    echo ".env not found. Create it first: cp .env.example .env" >&2
    exit 1
  fi
  if [[ ! -f config.yaml ]]; then
    echo "config.yaml not found. Please provide runtime config.yaml." >&2
    exit 1
  fi
  mkdir -p data logs
}

action="${1:-deploy}"

case "${action}" in
  build)
    ensure_files
    run_compose build --pull
    ;;
  up)
    ensure_files
    run_compose up -d --remove-orphans
    ;;
  deploy)
    ensure_files
    run_compose build --pull
    run_compose up -d --remove-orphans
    run_compose ps
    ;;
  down)
    run_compose down
    ;;
  restart)
    ensure_files
    run_compose restart
    ;;
  logs)
    run_compose logs -f --tail=200
    ;;
  ps|status)
    run_compose ps
    ;;
  *)
    cat <<'EOF'
Usage: scripts/docker-deploy.sh [action]

Actions:
  deploy   Build image and recreate container (default)
  build    Build image only
  up       Start container only
  down     Stop and remove container
  restart  Restart container
  logs     Follow logs
  status   Show container status
EOF
    exit 1
    ;;
esac
