#!/usr/bin/env bash
# Back up PostgreSQL, MinIO objects and configuration metadata into ./backups/<timestamp>.
set -euo pipefail

cd "$(dirname "$0")/.."
TS="$(date +%Y%m%d-%H%M%S)"
DEST="backups/${TS}"
mkdir -p "${DEST}"

echo "Backing up PostgreSQL → ${DEST}/postgres.dump"
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-scopeguard}" -Fc \
  "${POSTGRES_DB:-scopeguard}" > "${DEST}/postgres.dump"

echo "Backing up MinIO objects → ${DEST}/minio/"
mkdir -p "${DEST}/minio"
# Use a throwaway mc container sharing the compose network.
docker run --rm --network scopeguard_default \
  -v "$(pwd)/${DEST}/minio:/out" \
  --entrypoint sh minio/mc -c "
    mc alias set local http://minio:9000 '${MINIO_ACCESS_KEY:-scopeguard}' '${MINIO_SECRET_KEY:-scopeguard-dev-secret}' >/dev/null &&
    mc mirror --quiet local/'${MINIO_BUCKET:-scopeguard-documents}' /out || true
  " 2>/dev/null || echo "  (MinIO mirror skipped — bucket may be empty or network name differs)"

echo "Capturing configuration metadata → ${DEST}/env.snapshot"
grep -vE '^(SECRET_KEY|.*PASSWORD|.*SECRET_KEY|.*ACCESS_KEY)=' .env 2>/dev/null > "${DEST}/env.snapshot" || true

echo "Backup complete: ${DEST}"
