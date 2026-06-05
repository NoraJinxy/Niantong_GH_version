#!/usr/bin/env bash
# Purpose: Apply a local deployment profile so developers can run ELYS with matching environment variables.
# Related: deploy/profiles/local.env, deploy/deploy.sh, backend/app/config.py.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROFILE_PATH="${1:-${SCRIPT_DIR}/profiles/local.env}"

if [[ ! -f "${PROFILE_PATH}" ]]; then
  echo "Profile not found: ${PROFILE_PATH}" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${PROFILE_PATH}"
set +a

: "${APP_ENV:=local}"
: "${ENTRY_ORIGIN:=http://localhost:3000}"
: "${DATA_ORIGIN:=http://localhost:3000}"
: "${VITE_API_BASE_URL:=/api/v1}"
: "${VITE_DATA_API_BASE_URL:=/api/v1}"
: "${DB_HOST:=127.0.0.1}"
: "${DB_PORT:=5432}"
: "${DB_NAME:=elys}"
: "${DB_USER:=postgres}"
: "${DB_PASSWORD:=postgres}"
: "${REDIS_HOST:=127.0.0.1}"
: "${REDIS_PORT:=6379}"
: "${CELERY_WORKFLOW_QUEUE:=workflow.default}"
: "${PIPELINE_EXECUTION_MODE:=auto}"
: "${CELERY_WORKER_PING_TIMEOUT_SECONDS:=0.5}"
: "${STUDIES_DIR:=${HOME}/elys_data/studies}"
: "${CORS_ORIGINS:=http://localhost:3000,http://127.0.0.1:3000}"
: "${SECRET_KEY:=local-dev-change-me}"
: "${DEBUG:=true}"

mkdir -p "${STUDIES_DIR}"

cat > "${PROJECT_ROOT}/backend/.env" <<EOF
APP_ENV=${APP_ENV}
APP_NAME=Elys
VERSION=1.0.0
DEBUG=${DEBUG}

DB_HOST=${DB_HOST}
DB_PORT=${DB_PORT}
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}

REDIS_HOST=${REDIS_HOST}
REDIS_PORT=${REDIS_PORT}
CELERY_WORKFLOW_QUEUE=${CELERY_WORKFLOW_QUEUE}
PIPELINE_EXECUTION_MODE=${PIPELINE_EXECUTION_MODE}
CELERY_WORKER_PING_TIMEOUT_SECONDS=${CELERY_WORKER_PING_TIMEOUT_SECONDS}

STUDIES_DIR=${STUDIES_DIR}
CORS_ORIGINS=${CORS_ORIGINS}
SECRET_KEY=${SECRET_KEY}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
EOF

cat > "${PROJECT_ROOT}/frontend/elys-web/.env.local" <<EOF
VITE_API_BASE_URL=${VITE_API_BASE_URL}
VITE_DATA_API_BASE_URL=${VITE_DATA_API_BASE_URL}
VITE_APP_ORIGIN=${ENTRY_ORIGIN}
VITE_DATA_ORIGIN=${DATA_ORIGIN}
EOF

echo "Applied local profile: ${PROFILE_PATH}"
echo "Backend env: ${PROJECT_ROOT}/backend/.env"
echo "Frontend env: ${PROJECT_ROOT}/frontend/elys-web/.env.local"
echo "Studies dir: ${STUDIES_DIR}"
echo ""
echo "Next local commands:"
echo "  frontend: cd ${PROJECT_ROOT}/frontend/elys-web && npm run dev"
echo "  backend : cd ${PROJECT_ROOT}/backend && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
echo "  worker  : optional when PIPELINE_EXECUTION_MODE=auto; start Redis and celery for async stress testing"
