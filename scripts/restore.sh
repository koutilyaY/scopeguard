#!/usr/bin/env bash
# Restore PostgreSQL (and MinIO objects if present) from a backup directory.
# Usage: ./scripts/restore.sh backups/<timestamp>
set -euo pipefail

cd "$(dirname "$0")/.."
SRC="${1:?Usage: restore.sh backups/<timestamp>}"

if [ ! -f "${SRC}/postgres.dump" ]; then
  echo "No postgres.dump found in ${SRC}" >&2
  exit 1
fi

echo "Restoring PostgreSQL from ${SRC}/postgres.dump"
docker compose exec -T postgres psql -U "${POSTGRES_USER:-scopeguard}" -d "${POSTGRES_DB:-scopeguard}" \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker compose exec -T postgres pg_restore -U "${POSTGRES_USER:-scopeguard}" \
  -d "${POSTGRES_DB:-scopeguard}" --no-owner < "${SRC}/postgres.dump"

if [ -d "${SRC}/minio" ]; then
  echo "Restoring MinIO objects from ${SRC}/minio/"
  docker run --rm --network scopeguard_default \
    -v "$(pwd)/${SRC}/minio:/in" \
    --entrypoint sh minio/mc -c "
      mc alias set local http://minio:9000 '${MINIO_ACCESS_KEY:-scopeguard}' '${MINIO_SECRET_KEY:-scopeguard-dev-secret}' >/dev/null &&
      mc mb --ignore-existing local/'${MINIO_BUCKET:-scopeguard-documents}' &&
      mc mirror --quiet /in local/'${MINIO_BUCKET:-scopeguard-documents}'
    " 2>/dev/null || echo "  (MinIO restore skipped)"
fi

echo "Restore complete from ${SRC}"
