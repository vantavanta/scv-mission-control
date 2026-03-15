#!/bin/bash
# Start the SCV Mission Control dashboard on port 8888
# Access from any device on your LAN: http://<your-ip>:8888
cd "$(dirname "$0")"
echo "SCV Mission Control running at http://localhost:8888"
echo "LAN access: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'your-ip'):8888"
python3 -m http.server 8888 --bind 0.0.0.0
