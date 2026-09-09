#!/bin/bash
# Dashboard Backend Setup (launchd)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="ai.hermes.dashboard-backend"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

echo "=== Mobile Dashboard Backend Setup ==="

# Check .env
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "ERROR: .env file missing. Copy .env.example to .env and fill in values."
  exit 1
fi

# Load env vars
set -a
source "$SCRIPT_DIR/.env"
set +a

# Verify
[ -z "$SUPABASE_URL" ] && echo "ERROR: SUPABASE_URL not set" && exit 1
[ -z "$SUPABASE_SERVICE_KEY" ] && echo "ERROR: SUPABASE_SERVICE_KEY not set" && exit 1

# Create plist
cat > "$PLIST_PATH" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>${SCRIPT_DIR}/backend.py</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>SUPABASE_URL</key>
        <string>${SUPABASE_URL}</string>
        <key>SUPABASE_SERVICE_KEY</key>
        <string>${SUPABASE_SERVICE_KEY}</string>
        <key>OMNIROUTE_URL</key>
        <string>${OMNIROUTE_URL:-http://localhost:20128}</string>
        <key>OMNIROUTE_PASSWORD</key>
        <string>${OMNIROUTE_PASSWORD:-CHANGEME}</string>
    </dict>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${SCRIPT_DIR}/data/backend.log</string>
    <key>StandardErrorPath</key>
    <string>${SCRIPT_DIR}/data/backend.err</string>
    <key>ThrottleInterval</key>
    <integer>60</integer>
</dict>
</plist>
PLIST

echo "Plist written to: $PLIST_PATH"

# Unload if exists, then load
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo "Backend started! Check logs: ${SCRIPT_DIR}/data/backend.log"
echo "To stop: launchctl unload $PLIST_PATH"
