#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
DOCKER_BIN="${DOCKER_BIN:-/usr/bin/docker}"
LOCK_FILE="${PIPELINE_LOCK_FILE:-/tmp/london-environment-pipeline.lock}"

if [[ ! -f "${PROJECT_DIR}/.env" ]]; then
  echo "Missing ${PROJECT_DIR}/.env" >&2
  exit 1
fi

cd "${PROJECT_DIR}"

# A delayed run must not overlap the next scheduled run.
flock --nonblock "${LOCK_FILE}" \
  "${DOCKER_BIN}" compose -f docker-compose.prod.yml run --rm pipeline
