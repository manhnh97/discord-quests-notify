#!/bin/bash

# Discord Quests Cron Job Setup Script
# This script helps set up a cron job to run the Discord quests checker every 30 minutes

echo "Setting up Discord Quests Cron Job..."

# Get the current directory (where the script is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/main.py"

# Find Python executable (try common locations)
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python not found. Please install Python 3."
    exit 1
fi

echo "Using Python: $PYTHON_CMD"
echo "Script location: $PYTHON_SCRIPT"

# Create the cron job entry
CRON_ENTRY="*/30 * * * * cd $SCRIPT_DIR && $PYTHON_CMD $PYTHON_SCRIPT >> $SCRIPT_DIR/cron.log 2>&1"

echo "Cron job entry:"
echo "$CRON_ENTRY"
echo ""

# Add to crontab
echo "Adding cron job..."
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

if [ $? -eq 0 ]; then
    echo "✅ Cron job added successfully!"
    echo ""
    echo "The script will run every 30 minutes."
    echo "Logs will be saved to: $SCRIPT_DIR/cron.log"
    echo "Application logs will be saved to: $SCRIPT_DIR/discord_quests.log"
    echo ""
    echo "To view current cron jobs: crontab -l"
    echo "To remove this cron job: crontab -e (then delete the line)"
else
    echo "❌ Failed to add cron job. Please run manually:"
    echo "crontab -e"
    echo "Then add this line:"
    echo "$CRON_ENTRY"
fi

