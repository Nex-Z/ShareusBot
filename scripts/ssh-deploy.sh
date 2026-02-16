#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/ssh-deploy.sh --host <server> --user <user> [options]

Required:
  --host            Remote server host/IP
  --user            Remote SSH user

Options:
  --port            SSH port (default: 22)
  --identity        SSH private key path (optional)
  --remote-dir      Remote deploy directory (default: /opt/shareusbot)
  --image-name      Docker image name (default: shareusbot)
  --image-tag       Docker image tag (default: latest)
  --platform        Target platform: auto|linux/amd64|linux/arm64 (default: auto)
  --transfer-mode   Image transfer mode: scp|stream (default: scp)
  --project-name    Docker compose project name (default: shareusbot)
  --container-name  Container name (default: shareusbot)
  --no-build        Skip local build and use local existing image
  -h, --help        Show this help

Example:
  bash scripts/ssh-deploy.sh \
    --host 1.2.3.4 \
    --user root \
    --remote-dir /opt/shareusbot \
    --image-name shareusbot \
    --image-tag 20260216 \
    --platform linux/amd64
EOF
}

HOST=""
USER_NAME=""
SSH_PORT="22"
SSH_IDENTITY=""
REMOTE_DIR="/usr/local/project/shareusbot"
IMAGE_NAME="shareusbot"
IMAGE_TAG="latest"
PLATFORM="auto"
TRANSFER_MODE="scp"
PROJECT_NAME="shareusbot"
CONTAINER_NAME="shareusbot"
SKIP_BUILD="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="${2:-}"
      shift 2
      ;;
    --user)
      USER_NAME="${2:-}"
      shift 2
      ;;
    --port)
      SSH_PORT="${2:-}"
      shift 2
      ;;
    --identity)
      SSH_IDENTITY="${2:-}"
      shift 2
      ;;
    --remote-dir)
      REMOTE_DIR="${2:-}"
      shift 2
      ;;
    --image-name)
      IMAGE_NAME="${2:-}"
      shift 2
      ;;
    --image-tag)
      IMAGE_TAG="${2:-}"
      shift 2
      ;;
    --platform)
      PLATFORM="${2:-}"
      shift 2
      ;;
    --transfer-mode)
      TRANSFER_MODE="${2:-}"
      shift 2
      ;;
    --project-name)
      PROJECT_NAME="${2:-}"
      shift 2
      ;;
    --container-name)
      CONTAINER_NAME="${2:-}"
      shift 2
      ;;
    --no-build)
      SKIP_BUILD="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${HOST}" || -z "${USER_NAME}" ]]; then
  echo "--host and --user are required." >&2
  usage
  exit 1
fi

if [[ "${PLATFORM}" != "auto" && "${PLATFORM}" != "linux/amd64" && "${PLATFORM}" != "linux/arm64" ]]; then
  echo "Invalid --platform: ${PLATFORM}" >&2
  exit 1
fi

if [[ "${TRANSFER_MODE}" != "scp" && "${TRANSFER_MODE}" != "stream" ]]; then
  echo "Invalid --transfer-mode: ${TRANSFER_MODE}" >&2
  exit 1
fi

for cmd in docker ssh scp; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Missing required command: ${cmd}" >&2
    exit 1
  fi
done

if [[ ! -f ".env" ]]; then
  echo ".env not found. Create it first: cp .env.example .env" >&2
  exit 1
fi

if [[ ! -f "config.yaml" ]]; then
  echo "config.yaml not found. Please provide runtime config.yaml." >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  LOCAL_COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  LOCAL_COMPOSE=(docker-compose)
else
  echo "docker compose (or docker-compose) is required locally." >&2
  exit 1
fi

echo "[preflight] Validating .env interpolation with compose"
COMPOSE_ERR_FILE="$(mktemp "/tmp/shareusbot-compose-check.XXXXXX.err")"
if ! "${LOCAL_COMPOSE[@]}" -f docker-compose.yml config >/dev/null 2>"${COMPOSE_ERR_FILE}"; then
  cat "${COMPOSE_ERR_FILE}" >&2
  rm -f "${COMPOSE_ERR_FILE}"
  echo "compose config validation failed." >&2
  exit 1
fi

if grep -Eqi "variable is not set|defaulting to a blank string" "${COMPOSE_ERR_FILE}"; then
  cat "${COMPOSE_ERR_FILE}" >&2
  rm -f "${COMPOSE_ERR_FILE}"
  echo "Detected unresolved variable interpolation in .env." >&2
  echo "Quote secrets containing '\$' with single quotes, e.g. KEY='abc\$def'." >&2
  exit 1
fi
rm -f "${COMPOSE_ERR_FILE}"

IMAGE_REF="${IMAGE_NAME}:${IMAGE_TAG}"
SSH_TARGET="${USER_NAME}@${HOST}"
CONTROL_PATH="/tmp/ssh-cmux-shareusbot-${USER_NAME}-${HOST//[^a-zA-Z0-9]/_}-${SSH_PORT}-$$"
TMP_IMAGE_FILE=""

SSH_BASE_OPTS=(-p "${SSH_PORT}" -o ControlPath="${CONTROL_PATH}" -o ControlPersist=10m -o ServerAliveInterval=30)
if [[ -n "${SSH_IDENTITY}" ]]; then
  SSH_BASE_OPTS+=(-i "${SSH_IDENTITY}")
fi
SSH_CMD_OPTS=("${SSH_BASE_OPTS[@]}" -o ControlMaster=auto)
SCP_CMD_OPTS=(-P "${SSH_PORT}" -o ControlPath="${CONTROL_PATH}" -o ControlPersist=10m -o ServerAliveInterval=30)
if [[ -n "${SSH_IDENTITY}" ]]; then
  SCP_CMD_OPTS+=(-i "${SSH_IDENTITY}")
fi

cleanup() {
  if [[ -n "${TMP_IMAGE_FILE}" && -f "${TMP_IMAGE_FILE}" ]]; then
    rm -f "${TMP_IMAGE_FILE}"
  fi
  ssh "${SSH_BASE_OPTS[@]}" -O exit "${SSH_TARGET}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[0/6] Opening SSH control connection (password only once with password auth)"
ssh "${SSH_BASE_OPTS[@]}" -o ControlMaster=yes -Nf "${SSH_TARGET}"

ssh_run() {
  ssh "${SSH_CMD_OPTS[@]}" "${SSH_TARGET}" "$@"
}

scp_run() {
  scp "${SCP_CMD_OPTS[@]}" "$@"
}

if [[ "${PLATFORM}" == "auto" ]]; then
  REMOTE_ARCH="$(ssh_run "uname -m" | tr -d '\r\n')"
  case "${REMOTE_ARCH}" in
    x86_64|amd64)
      PLATFORM="linux/amd64"
      ;;
    aarch64|arm64)
      PLATFORM="linux/arm64"
      ;;
    *)
      echo "Unsupported remote arch: ${REMOTE_ARCH}. Please pass --platform explicitly." >&2
      exit 1
      ;;
  esac
  echo "[0/6] Remote arch=${REMOTE_ARCH}, platform=${PLATFORM}"
fi

if [[ "${SKIP_BUILD}" != "true" ]]; then
  echo "[1/6] Building local image: ${IMAGE_REF} (${PLATFORM})"
  if ! docker buildx version >/dev/null 2>&1; then
    echo "docker buildx is required for cross-platform build." >&2
    exit 1
  fi
  docker buildx inspect >/dev/null 2>&1 || docker buildx create --use >/dev/null
  docker buildx build --platform "${PLATFORM}" -t "${IMAGE_REF}" --load -f Dockerfile .
else
  echo "[1/6] Skip build, using local image: ${IMAGE_REF}"
fi

echo "[2/6] Ensuring remote directories: ${REMOTE_DIR}"
ssh_run "mkdir -p '${REMOTE_DIR}/data' '${REMOTE_DIR}/logs'"

echo "[3/6] Uploading runtime files (.env, config.yaml, docker-compose.yml)"
scp_run .env config.yaml docker-compose.yml "${SSH_TARGET}:${REMOTE_DIR}/"

IMAGE_SIZE_BYTES="$(docker image inspect "${IMAGE_REF}" --format '{{.Size}}' 2>/dev/null || echo 0)"
if [[ "${TRANSFER_MODE}" == "scp" ]]; then
  if [[ "${IMAGE_SIZE_BYTES}" =~ ^[0-9]+$ && "${IMAGE_SIZE_BYTES}" -gt 0 ]]; then
    IMAGE_SIZE_MIB=$((IMAGE_SIZE_BYTES / 1024 / 1024))
    echo "[4/6] Exporting image archive (~${IMAGE_SIZE_MIB} MiB uncompressed)"
  else
    echo "[4/6] Exporting image archive"
  fi

  TMP_IMAGE_FILE="$(mktemp "/tmp/shareusbot-image.XXXXXX.tar.gz")"
  docker save "${IMAGE_REF}" | gzip > "${TMP_IMAGE_FILE}"

  echo "[4/6] Uploading image archive via scp (progress is shown by scp)"
  scp_run "${TMP_IMAGE_FILE}" "${SSH_TARGET}:${REMOTE_DIR}/image.tar.gz"

  echo "[4/6] Loading image on remote docker daemon"
  ssh_run "gzip -dc '${REMOTE_DIR}/image.tar.gz' | docker load && rm -f '${REMOTE_DIR}/image.tar.gz'"
else
  if [[ "${IMAGE_SIZE_BYTES}" =~ ^[0-9]+$ && "${IMAGE_SIZE_BYTES}" -gt 0 ]]; then
    IMAGE_SIZE_MIB=$((IMAGE_SIZE_BYTES / 1024 / 1024))
    echo "[4/6] Streaming image to remote docker daemon (~${IMAGE_SIZE_MIB} MiB uncompressed)"
  else
    echo "[4/6] Streaming image to remote docker daemon"
  fi

  docker save "${IMAGE_REF}" | gzip | ssh "${SSH_CMD_OPTS[@]}" "${SSH_TARGET}" "gzip -d | docker load"
fi

echo "[5/6] Starting remote services"
ssh "${SSH_CMD_OPTS[@]}" "${SSH_TARGET}" "bash -s" <<EOF
set -euo pipefail
cd '${REMOTE_DIR}'
if docker compose version >/dev/null 2>&1; then
  COMPOSE='docker compose'
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE='docker-compose'
else
  echo 'docker compose not found on remote host' >&2
  exit 1
fi
export IMAGE_NAME='${IMAGE_NAME}' IMAGE_TAG='${IMAGE_TAG}' CONTAINER_NAME='${CONTAINER_NAME}'
\$COMPOSE -p '${PROJECT_NAME}' -f docker-compose.yml up -d --remove-orphans --no-build
\$COMPOSE -p '${PROJECT_NAME}' -f docker-compose.yml ps
EOF

echo "[6/6] Done"
echo "Remote deploy completed: ${SSH_TARGET}:${REMOTE_DIR}"
