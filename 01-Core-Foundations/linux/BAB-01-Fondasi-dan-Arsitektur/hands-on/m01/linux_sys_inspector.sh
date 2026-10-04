#!/usr/bin/env bash
set -euo pipefail

echo "=== LINUX SYSTEM ARCHITECTURE & RESOURCE INSPECTOR ==="
echo "1. Kernel Version: $(uname -r)"
echo "2. CPU Cores & Model: $(grep -m 1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs)"
echo "3. Memory Utilization:"
free -h
echo "4. Virtual Filesystem Mounts (Top 5):"
df -h | head -n 6
echo "5. Active Load Average:"
cat /proc/loadavg
echo "=== INSPEKSI SELESAI ==="
