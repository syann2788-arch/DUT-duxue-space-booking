#!/bin/sh
set -eu

: "${POSTGRES_BACKUP_URL:?POSTGRES_BACKUP_URL is required}"
: "${BACKUP_DIR:?BACKUP_DIR is required}"
: "${PRIVATE_UPLOAD_DIR:?PRIVATE_UPLOAD_DIR is required}"
: "${BACKUP_AGE_RECIPIENT:?BACKUP_AGE_RECIPIENT is required}"

umask 077
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT INT TERM
mkdir -p "$BACKUP_DIR"

pg_dump --format=custom --no-owner --file="$workdir/database.dump" "$POSTGRES_BACKUP_URL"
tar -C "$PRIVATE_UPLOAD_DIR" -czf "$workdir/private-media.tar.gz" .
age -r "$BACKUP_AGE_RECIPIENT" -o "$BACKUP_DIR/database-$timestamp.dump.age" "$workdir/database.dump"
age -r "$BACKUP_AGE_RECIPIENT" -o "$BACKUP_DIR/private-media-$timestamp.tar.gz.age" "$workdir/private-media.tar.gz"
find "$BACKUP_DIR" -type f -name '*.age' -mtime +14 -delete
