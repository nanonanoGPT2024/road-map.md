#!/usr/bin/env bash
# Standar Defensive Bash (GEMINI.md)
set -euo pipefail

BACKUP_SRC="/tmp/test_backup_src"
BACKUP_DST="/tmp/test_backup_dst"

mkdir -p "$BACKUP_SRC" "$BACKUP_DST"
echo "data-penting-$(date)" > "$BACKUP_SRC/app.log"

echo "[INFO] Memulai backup defensif..."
tar -czf "$BACKUP_DST/backup-$(date +%s).tar.gz" -C "$BACKUP_SRC" .
echo "[SUCCESS] Backup berhasil dibuat di $BACKUP_DST"

rm -rf "$BACKUP_SRC" "$BACKUP_DST"
