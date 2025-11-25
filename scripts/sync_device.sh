#!/bin/bash
# Sync local Claude data to the repository
# Run this on each device to push data

# Configuration - CHANGE THESE
DEVICE_NAME="${DEVICE_NAME:-$(hostname)}"
REPO_PATH="${REPO_PATH:-$HOME/claude-session-dashboard}"
CLAUDE_DATA="$HOME/.claude/projects"

echo "=== Claude Data Sync ==="
echo "Device: $DEVICE_NAME"
echo "Repo: $REPO_PATH"
echo "Source: $CLAUDE_DATA"
echo ""

# Check if claude data exists
if [ ! -d "$CLAUDE_DATA" ]; then
    echo "ERROR: Claude data not found at $CLAUDE_DATA"
    exit 1
fi

# Navigate to repo
cd "$REPO_PATH" || { echo "ERROR: Repo not found at $REPO_PATH"; exit 1; }

# Pull latest
echo "Pulling latest changes..."
git pull --rebase

# Create device directory
DEVICE_DIR="$REPO_PATH/data/$DEVICE_NAME"
mkdir -p "$DEVICE_DIR"

# Sync Claude projects data
echo "Syncing Claude data..."
rsync -av --delete "$CLAUDE_DATA/" "$DEVICE_DIR/projects/"

# Commit and push
echo "Committing changes..."
git add "data/$DEVICE_NAME/"
git commit -m "Update data from $DEVICE_NAME - $(date '+%Y-%m-%d %H:%M')" || echo "No changes to commit"

echo "Pushing to remote..."
git push

echo ""
echo "=== Sync complete! ==="
