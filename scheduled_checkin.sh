#!/bin/bash
# Blind scheduled symptom check-in — every 30 minutes via cron
# NO RF information shown to subject. Just asks "how are you feeling?"
# This eliminates notification bias from the ML analysis.

NTFY_URL="http://100.96.113.92:8090/artemis-checkin"
TAG_URL="http://100.96.113.92:8091/live"

# Silent notification — default priority, no alarm sound
curl -s -X POST "$NTFY_URL" \
  -H "Title: How are you feeling?" \
  -H "Priority: low" \
  -H "Tags: clipboard" \
  -H "Actions: view, Log symptoms, $TAG_URL, clear=true" \
  -d "Scheduled check-in. Tap to log current symptoms." \
  > /dev/null 2>&1
