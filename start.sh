#!/usr/bin/env bash
set -e

# Create data dir if missing
mkdir -p data

# If CREDENTIALS_JSON env var present, write to credentials.json
if [ -n "$CREDENTIALS_JSON" ]; then
  echo "Writing credentials.json from env"
  echo "$CREDENTIALS_JSON" > credentials.json
fi

# If TOKEN_JSON env var present, write to token.json
if [ -n "$TOKEN_JSON" ]; then
  echo "Writing token.json from env"
  echo "$TOKEN_JSON" > token.json
fi

# Ensure memory/scan_history files exist so the app doesn't error
touch data/memory.json || true
touch data/community_memory.json || true
touch data/scan_history.json || true
touch data/rules.json || true

# Run gunicorn
exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4
