#!/bin/bash
set -euo pipefail

# ── RF Monitor Hardened Entrypoint ────────────────────────────────────
# - Verifies code integrity on startup
# - Checks SDR hardware availability
# - Auto-restarts sentinel on failure
# - Logs everything

HASH_FILE="/app/.code_hashes"
LOG="/data/results/entrypoint.log"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG"; }

# ── Step 1: Verify code hasn't been tampered with ────────────────────
if [ -f "$HASH_FILE" ]; then
    log "Verifying code integrity..."
    CURRENT=$(find /app -name "*.py" -exec sha256sum {} + | sort | sha256sum | cut -d' ' -f1)
    STORED=$(cat "$HASH_FILE")
    if [ "$CURRENT" != "$STORED" ]; then
        log "CRITICAL: Code integrity check FAILED!"
        log "  Expected: $STORED"
        log "  Got:      $CURRENT"
        log "  Someone modified the Python code inside the container."
        exit 99
    fi
    log "Code integrity: OK"
else
    log "First run — generating code hash baseline..."
    find /app -name "*.py" -exec sha256sum {} + | sort | sha256sum | cut -d' ' -f1 > "$HASH_FILE"
    log "Baseline saved to $HASH_FILE"
fi

# ── Step 2: Check SDR hardware ───────────────────────────────────────
log "Checking SDR hardware..."
MAX_RETRIES=30
RETRY=0
while ! rtl_test -t 2>&1 | grep -q "Found\|Realtek"; do
    RETRY=$((RETRY + 1))
    if [ $RETRY -ge $MAX_RETRIES ]; then
        log "WARN: SDR not detected after ${MAX_RETRIES} attempts. Starting anyway (will retry in sentinel)."
        break
    fi
    log "SDR not ready (attempt $RETRY/$MAX_RETRIES), waiting 10s..."
    sleep 10
done

if rtl_test -t 2>&1 | grep -q "Found\|Realtek"; then
    log "SDR detected: $(rtl_test -t 2>&1 | head -3 | tr '\n' ' ')"
fi

# ── Step 3: Verify data integrity if previous data exists ────────────
if ls /data/results/sentinel_*.jsonl 1>/dev/null 2>&1; then
    log "Verifying existing data integrity..."
    python /app/verify_integrity.py --results-dir /data/results 2>&1 | tee -a "$LOG"
fi

# ── Step 4: Generate evidence hash manifest ──────────────────────────
log "Generating pre-run hash manifest..."
python /app/verify_integrity.py --results-dir /data/results --generate-manifest \
    --output "/data/results/evidence/hashes_$(date -u +%Y%m%d_%H%M%S).txt" 2>&1 | tee -a "$LOG"

# ── Step 5: Launch requested command ─────────────────────────────────
log "Launching: python $*"
exec python "$@"
