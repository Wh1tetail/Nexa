#!/bin/sh
# Backups for the docker compose `backup` service: a PostgreSQL dump and an
# archive of uploaded files every BACKUP_INTERVAL_HOURS, written to /backups
# (BACKUP_DIR on the host). Copies older than BACKUP_KEEP_DAYS are deleted.
# Restore: see "Резервные копии" in README.md.
set -u

KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
INTERVAL_HOURS="${BACKUP_INTERVAL_HOURS:-24}"
export PGPASSWORD="$POSTGRES_PASSWORD"

backup_once() {
    ts=$(date -u +%Y%m%d-%H%M%S)
    # write to *.part first, so a half-written file never looks like a backup
    if pg_dump -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner \
            -f "/backups/db-$ts.dump.part"; then
        mv "/backups/db-$ts.dump.part" "/backups/db-$ts.dump"
        echo "[backup] database -> db-$ts.dump"
    else
        rm -f "/backups/db-$ts.dump.part"
        echo "[backup] ERROR: database dump failed" >&2
    fi
    if tar -czf "/backups/files-$ts.tar.gz.part" -C /uploads .; then
        mv "/backups/files-$ts.tar.gz.part" "/backups/files-$ts.tar.gz"
        echo "[backup] files -> files-$ts.tar.gz"
    else
        rm -f "/backups/files-$ts.tar.gz.part"
        echo "[backup] ERROR: files archive failed" >&2
    fi
    find /backups -maxdepth 1 \( -name 'db-*.dump' -o -name 'files-*.tar.gz' \) \
        -mtime +"$KEEP_DAYS" -print -delete | sed 's/^/[backup] removed old /'
}

mkdir -p /backups
until pg_isready -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; do
    sleep 2
done

while true; do
    backup_once
    sleep $((INTERVAL_HOURS * 3600))
done
