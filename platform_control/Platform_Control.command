#!/bin/bash
# =============================================================================
# AI Platform Control - Launch Script
# =============================================================================
# Double-click this file to launch the Platform Control Panel
# =============================================================================

cd "$(dirname "$0")"

# Check if customtkinter is installed
python3 -c "import customtkinter" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing customtkinter..."
    pip3 install customtkinter httpx
fi

# Launch the app
python3 main.py
