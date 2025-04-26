#!/usr/bin/env python3
"""
Development wrapper for the auction bot that sets up development environment
"""

import os
import subprocess
import platform

# Development settings
os.environ['ENABLE_VPN_CHECK'] = 'False'

# Determine if we're on a headless server
is_headless_server = 'DISPLAY' not in os.environ or not os.environ['DISPLAY']
if platform.system() == 'Linux' and is_headless_server:
    os.environ['HEADLESS_BROWSER'] = 'True'
else:
    os.environ['HEADLESS_BROWSER'] = 'True'  # Default to headless, change to False if you want GUI

# Run the main application
if __name__ == "__main__":
    print("🛠️  Running in development mode with VPN check disabled")
    import main
    main.asyncio.run(main.main())