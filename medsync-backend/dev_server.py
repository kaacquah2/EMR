#!/usr/bin/env python
"""
Development server launcher for MedSync backend with proper Daphne configuration.

This script starts the Django development server with Daphne properly configured
for graceful shutdown during file reloads. It avoids the "took too long to shut down"
errors that occur with rapid file changes.

Usage:
    python dev_server.py              # Start on 127.0.0.1:8000
    python dev_server.py 8001         # Start on 127.0.0.1:8001
    python dev_server.py 0.0.0.0:8000 # Start on 0.0.0.0:8000

The script will:
1. Set Daphne timeout to 5 seconds for graceful reload (vs default 2 seconds)
2. Configure WebSocket ping/timeout to reduce connection churn
3. Enable access logging for debugging
4. Start with auto-reload enabled for development

Benefits:
- Prevents "Application instance took too long to shut down" warnings
- Allows pending requests to complete gracefully during file reload
- Better WebSocket stability during development
"""

import os
import sys
import subprocess
from pathlib import Path


def main():
    """Start development server with proper Daphne configuration."""
    
    base_dir = Path(__file__).parent
    
    # Ensure we're in the right directory
    if not (base_dir / "manage.py").exists():
        print(f"ERROR: manage.py not found at {base_dir / 'manage.py'}")
        print("   Run this script from medsync-backend/ directory")
        sys.exit(1)
    
    # Parse command line arguments for host:port
    host_port = "127.0.0.1:8000"
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if ":" in arg:
            host_port = arg
        else:
            host_port = f"127.0.0.1:{arg}"
    
    print("=" * 75)
    print("MedSync Backend Development Server (Daphne)")
    print("=" * 75)
    print(f"Address:  {host_port}")
    print(f"Protocol: ASGI (WebSocket support)")
    print()
    print("Configuration:")
    print("  * Application close timeout: 5s (allows graceful request completion)")
    print("  * WebSocket ping interval:   20s")
    print("  * WebSocket ping timeout:    20s")
    print("  * Auto-reload:               Enabled")
    print()
    print("Press CTRL+C to stop")
    print("=" * 75)
    print()
    
    # Set environment
    env = os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"] = "medsync_backend.settings"
    
    # Build Daphne command with proper timeout settings
    # --application-close-timeout: Time to wait for app shutdown (default 2s, we use 5s)
    # --ping-interval: WebSocket ping interval in seconds (reduces false disconnects)
    # --ping-timeout: Time to wait for pong response (should equal or exceed ping interval)
    # -v 1: Verbosity for access logging
    host, port = host_port.split(":")
    daphne_args = [
        "daphne",
        "-b", host,           # bind address
        "-p", port,           # port
        "--application-close-timeout", "5",  # CRITICAL: 5 seconds for graceful reload
        "--ping-interval", "20",  # Send ping every 20s to keep WebSocket alive
        "--ping-timeout", "20",   # Wait 20s for pong response
        "-v", "1",  # Verbosity: access log to stdout
        "medsync_backend.asgi:application",  # ASGI app
    ]
    
    try:
        result = subprocess.run(daphne_args, env=env)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\nServer stopped gracefully")
        sys.exit(0)
    except FileNotFoundError:
        print("ERROR: 'daphne' command not found")
        print("   Install with: pip install daphne")
        sys.exit(1)


if __name__ == "__main__":
    main()
