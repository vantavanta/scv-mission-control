#!/bin/bash
# SCV Dashboard — start the web server on port 8888, bound to all interfaces.
# Access from any device on your LAN at http://<your-ip>:8888

cd "$(dirname "$0")"
echo "🦾 SCV Mission Control — starting on http://0.0.0.0:8888"
echo "   Access from LAN: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'your-ip'):8888"
echo "   Press Ctrl+C to stop"
echo ""
python3 -m http.server 8888 --bind 0.0.0.0
