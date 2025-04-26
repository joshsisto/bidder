#!/bin/bash
# Development wrapper for the auction bot that sets up development environment

# Development settings
export ENABLE_VPN_CHECK=False
export HEADLESS_BROWSER=True  # Force headless mode for Linux servers

# Run the application
echo "🛠️  Running in development mode with VPN check disabled"
python main.py