#!/bin/bash
# ARTEMIS auto-push — runs hourly via cron
# Uses SSH deploy key (github-artemis) to push as targeted-phd

cd /home/tyler/projects/rf-monitor || exit 1

# Stage any new/modified files
git add -A

# Check if there's anything to commit
if git diff --cached --quiet; then
    exit 0
fi

# Commit with timestamp
git commit -m "auto: $(date '+%Y-%m-%d %H:%M') snapshot"

# Push via SSH deploy key
git push origin main
