#!/bin/sh
set -eu

exec python3 "$(dirname "$0")/backup_restore.py" backup
