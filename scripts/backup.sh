#!/bin/bash
# ABA Agent — Daily backup script
# Backs up SQLite database + vault storage, retains 30 days.
# Add to crontab: 0 2 * * * /root/ABA-Agent-Starter/scripts/backup.sh >> /var/log/aba-backup.log 2>&1

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/root/backups/aba}"
APP_DIR="${APP_DIR:-/root/ABA-Agent-Starter/api}"
DB_PATH="${APP_DIR}/aba_prod.db"
VAULT_PATH="${APP_DIR}/storage"
DATE=$(date +%Y-%m-%d_%H%M%S)
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup..."

# 1. SQLite online backup (safe while DB is in use)
if [ -f "$DB_PATH" ]; then
    sqlite3 "$DB_PATH" ".backup '${BACKUP_DIR}/db_${DATE}.sqlite3'"
    echo "[$(date)] DB backup: db_${DATE}.sqlite3 ($(du -h "${BACKUP_DIR}/db_${DATE}.sqlite3" | cut -f1))"
else
    echo "[$(date)] WARNING: Database not found at ${DB_PATH}, skipping DB backup"
fi

# 2. Vault files tarball
if [ -d "$VAULT_PATH" ]; then
    tar -czf "${BACKUP_DIR}/vault_${DATE}.tar.gz" -C "$VAULT_PATH" .
    echo "[$(date)] Vault backup: vault_${DATE}.tar.gz ($(du -h "${BACKUP_DIR}/vault_${DATE}.tar.gz" | cut -f1))"
else
    echo "[$(date)] WARNING: Vault storage not found at ${VAULT_PATH}, skipping vault backup"
fi

# 3. Cleanup old backups
deleted_db=$(find "$BACKUP_DIR" -name "db_*.sqlite3" -mtime +$RETENTION_DAYS -delete -print | wc -l)
deleted_vault=$(find "$BACKUP_DIR" -name "vault_*.tar.gz" -mtime +$RETENTION_DAYS -delete -print | wc -l)
if [ "$deleted_db" -gt 0 ] || [ "$deleted_vault" -gt 0 ]; then
    echo "[$(date)] Cleaned up: ${deleted_db} old DB + ${deleted_vault} old vault backups"
fi

echo "[$(date)] Backup completed successfully."
