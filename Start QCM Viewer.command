#!/bin/bash
# Double-clickable launcher for the QCM Viewer (macOS).
#
# First run: installs the uv package manager (one-time) and the app's
# dependencies, then opens the viewer in your browser. After that it starts in
# seconds. If macOS blocks the file ("unidentified developer"), right-click it
# and choose Open the first time.
set -e
cd "$(dirname "$0")"

# Finder launches don't load your shell profile, so common install locations
# of uv are added to PATH explicitly.
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
    echo "Installing the uv package manager (one-time setup)…"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

echo
echo "Starting the QCM Viewer — your browser will open shortly."
echo "(The first start downloads dependencies and can take a minute or two.)"
echo "Keep this window open while you work; close it to stop the viewer."
echo

# --port 0 picks a free port automatically, so a viewer that is already
# running (or anything else on the default port) never blocks startup.
exec uv run qcm view --port 0
