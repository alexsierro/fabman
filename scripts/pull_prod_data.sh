#!/usr/bin/env bash
# Copy production data into the local dev database (SQLite).
#
# Usage:   ./scripts/pull_prod_data.sh            (from Git Bash)
# Config:  scripts/pull_prod_data.env (gitignored), see pull_prod_data.env.dist
#
# Local code should be on the same version as prod so migrations match.
set -euo pipefail

cd "$(dirname "$0")/.."
source scripts/pull_prod_data.env

SSH="ssh -o IdentitiesOnly=yes -o BatchMode=yes $SSH_HOST"
REMOTE="cd $REMOTE_DIR && $COMPOSE -f docker-compose.prod.yml exec -T web"
DUMP="backup/prod_dump_$(date +%Y%m%d_%H%M%S).json"
PYTHON="venv/Scripts/python.exe"
[ -x "$PYTHON" ] || PYTHON="venv/bin/python"

mkdir -p backup

echo "==> Dumping production data to $DUMP"
# Dump to a file inside the container then cat it: settings.py prints to stdout.
$SSH "$REMOTE sh -c 'python manage.py dumpdata \
    --natural-foreign --natural-primary \
    --exclude contenttypes --exclude auth.permission \
    --exclude admin.logentry --exclude sessions \
    --output /tmp/dump.json > /dev/null && cat /tmp/dump.json && rm /tmp/dump.json'" > "$DUMP"

if [ "$WITH_MEDIA" = "true" ]; then
    echo "==> Downloading media files"
    $SSH "$REMOTE tar czf - -C /home/app/web media" | tar xzf - -C .
fi

echo "==> Recreating local database (old one saved in backup/)"
[ -f db.sqlite3 ] && mv db.sqlite3 "backup/db.sqlite3.$(date +%Y%m%d_%H%M%S).bak"
"$PYTHON" manage.py migrate --no-input

echo "==> Loading dump"
"$PYTHON" manage.py loaddata "$DUMP"

echo "Done."
