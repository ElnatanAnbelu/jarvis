#!/bin/bash
# JARVIS encrypted backup — local + (optionally) offsite.
# Backs up the Second Brain vault + jarvis.db as one AES-256 archive.
#
#   JARVIS_BACKUP_KEY   passphrase (REQUIRED for encryption; warns if unset)
#   JARVIS_BACKUP_DIR   output dir (default ~/JARVIS_Backups)
#   SECONDBRAIN_PATH    vault path (default ~/Documents/SecondBrain)
#
# Schedule it (e.g. cron / launchd) and point JARVIS_BACKUP_DIR at a synced
# folder (iCloud/Dropbox) for the "offsite" copy. Restore:
#   openssl enc -d -aes-256-cbc -pbkdf2 -in FILE.enc -pass pass:$KEY | tar -xzf -
set -euo pipefail

VAULT="${SECONDBRAIN_PATH:-$HOME/Documents/SecondBrain}"
DB="$HOME/jarvis/memory/jarvis.db"
DEST="${JARVIS_BACKUP_DIR:-$HOME/JARVIS_Backups}"
KEY="${JARVIS_BACKUP_KEY:-}"
STAMP="$(date +%Y%m%d-%H%M%S)"
ARCHIVE="$DEST/jarvis-backup-$STAMP.tar.gz"

mkdir -p "$DEST"

# Build the archive (vault always; db if present).
ITEMS=("$VAULT")
[ -f "$DB" ] && ITEMS+=("$DB")
tar -czf "$ARCHIVE" "${ITEMS[@]}" 2>/dev/null

if [ -n "$KEY" ]; then
  openssl enc -aes-256-cbc -pbkdf2 -salt -in "$ARCHIVE" -out "$ARCHIVE.enc" -pass "pass:$KEY"
  rm -f "$ARCHIVE"
  echo "✓ Encrypted backup: $ARCHIVE.enc"
else
  echo "⚠️  JARVIS_BACKUP_KEY not set — backup is UNENCRYPTED at $ARCHIVE"
fi

# Retain the 14 most recent backups.
ls -1t "$DEST"/jarvis-backup-* 2>/dev/null | tail -n +15 | xargs rm -f 2>/dev/null || true
echo "Backup complete → $DEST"
