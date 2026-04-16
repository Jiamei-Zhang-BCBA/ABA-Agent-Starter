#!/bin/bash
# ABA Agent — Restore from backup
# Usage: ./restore.sh <timestamp>
# Example: ./restore.sh 2026-04-15_020000

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/root/backups/aba}"
APP_DIR="${APP_DIR:-/root/ABA-Agent-Starter/api}"
TIMESTAMP="${1:-}"

if [ -z "$TIMESTAMP" ]; then
    echo "Usage: $0 <timestamp>"
    echo ""
    echo "Available backups:"
    if ls "${BACKUP_DIR}"/db_*.sqlite3 1>/dev/null 2>&1; then
        ls -lh "${BACKUP_DIR}"/db_*.sqlite3 | awk '{print "  " $NF " (" $5 ")"}'  | sed "s|${BACKUP_DIR}/db_||" | sed 's/.sqlite3//'
    else
        echo "  (none found)"
    fi
    exit 1
fi

DB_BACKUP="${BACKUP_DIR}/db_${TIMESTAMP}.sqlite3"
VAULT_BACKUP="${BACKUP_DIR}/vault_${TIMESTAMP}.tar.gz"

# Validate backups exist
if [ ! -f "$DB_BACKUP" ]; then
    echo "ERROR: DB backup not found: $DB_BACKUP"
    exit 1
fi

echo "=== ABA Agent Restore ==="
echo "  Timestamp: $TIMESTAMP"
echo "  DB backup: $DB_BACKUP ($(du -h "$DB_BACKUP" | cut -f1))"
if [ -f "$VAULT_BACKUP" ]; then
    echo "  Vault backup: $VAULT_BACKUP ($(du -h "$VAULT_BACKUP" | cut -f1))"
else
    echo "  Vault backup: (not found, skipping)"
fi
echo ""
read -p "Proceed with restore? This will overwrite current data. (y/N): " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Aborted."
    exit 0
fi

# Stop the service
echo "[1/4] Stopping service..."
sudo systemctl stop aba-api || true

# Backup current state before overwriting
echo "[2/4] Saving current state..."
ROLLBACK_DATE=$(date +%Y-%m-%d_%H%M%S)
if [ -f "${APP_DIR}/aba_prod.db" ]; then
    cp "${APP_DIR}/aba_prod.db" "${BACKUP_DIR}/db_pre-restore_${ROLLBACK_DATE}.sqlite3"
fi

# Restore DB
echo "[3/4] Restoring database..."
cp "$DB_BACKUP" "${APP_DIR}/aba_prod.db"

# Restore vault
if [ -f "$VAULT_BACKUP" ]; then
    echo "[3/4] Restoring vault files..."
    tar -xzf "$VAULT_BACKUP" -C "${APP_DIR}/storage"
fi

# Restart
echo "[4/4] Restarting service..."
sudo systemctl start aba-api

echo ""
echo "=== Restore completed ==="
echo "  Restored from: $TIMESTAMP"
echo "  Pre-restore backup: db_pre-restore_${ROLLBACK_DATE}.sqlite3"
echo "  Service status: $(systemctl is-active aba-api)"
