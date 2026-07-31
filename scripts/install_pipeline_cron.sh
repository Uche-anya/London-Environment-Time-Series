#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
RUNNER="${PROJECT_DIR}/scripts/run_production_pipeline.sh"
CRON_SCHEDULE="${PIPELINE_CRON_SCHEDULE:-0 6 * * *}"
LOG_FILE="${PIPELINE_LOG_FILE:-${HOME}/pipeline.log}"
CRON_MARKER="london-environment-pipeline-daily"
TEMP_CRONTAB="$(mktemp)"

cleanup() {
  rm -f -- "${TEMP_CRONTAB}"
}
trap cleanup EXIT

if [[ ! -f "${PROJECT_DIR}/.env" ]]; then
  echo "Create ${PROJECT_DIR}/.env before installing the schedule." >&2
  exit 1
fi

chmod +x "${RUNNER}"
crontab -l 2>/dev/null | grep -vF "${CRON_MARKER}" > "${TEMP_CRONTAB}" || true
printf '%s %q >> %q 2>&1 # %s\n' \
  "${CRON_SCHEDULE}" "${RUNNER}" "${LOG_FILE}" "${CRON_MARKER}" \
  >> "${TEMP_CRONTAB}"
crontab "${TEMP_CRONTAB}"

echo "Installed: ${CRON_SCHEDULE} ${RUNNER}"
echo "Logs: ${LOG_FILE}"
