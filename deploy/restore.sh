#!/bin/sh
set -eu

: "${POSTGRES_BACKUP_URL:?POSTGRES_BACKUP_URL is required}"
: "${DATABASE_BACKUP:?DATABASE_BACKUP is required}"
: "${MEDIA_BACKUP:?MEDIA_BACKUP is required}"
: "${PRIVATE_UPLOAD_DIR:?PRIVATE_UPLOAD_DIR is required}"
: "${BACKUP_AGE_IDENTITY:?BACKUP_AGE_IDENTITY is required}"

umask 077
workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT INT TERM
age -d -i "$BACKUP_AGE_IDENTITY" -o "$workdir/database.dump" "$DATABASE_BACKUP"
age -d -i "$BACKUP_AGE_IDENTITY" -o "$workdir/private-media.tar.gz" "$MEDIA_BACKUP"
pg_restore --clean --if-exists --no-owner --dbname="$POSTGRES_BACKUP_URL" "$workdir/database.dump"
mkdir -p "$PRIVATE_UPLOAD_DIR"
tar -C "$PRIVATE_UPLOAD_DIR" -xzf "$workdir/private-media.tar.gz"
alembic upgrade head
