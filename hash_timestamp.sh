#!/bin/bash
# Hourly evidence hash anchor — computes SHA-256 of latest sentinel data
# and appends to a timestamped log. Push to git for third-party anchoring.
# Add to cron: 0 * * * * /home/tyler/projects/rf-monitor/hash_timestamp.sh

set -euo pipefail
cd /home/tyler/projects/rf-monitor

LATEST=$(ls -t results/sentinel_*.jsonl 2>/dev/null | head -1)
[ -z "$LATEST" ] && exit 0

HASH=$(sha256sum "$LATEST" | cut -d' ' -f1)
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
FILE="results/evidence/hourly_hashes.log"

echo "$TS $HASH $(basename $LATEST) $(wc -l < "$LATEST")lines" >> "$FILE"

# Also hash the cumulative log itself
METAHASH=$(sha256sum "$FILE" | cut -d' ' -f1)
echo "  meta: $METAHASH" >> "$FILE"
