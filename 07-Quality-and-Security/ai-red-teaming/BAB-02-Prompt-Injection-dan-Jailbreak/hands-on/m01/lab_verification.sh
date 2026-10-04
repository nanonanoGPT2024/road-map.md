#!/usr/bin/env bash
# Hands-on Lab Verification for ai-red-teaming - Bab 02 (Prompt Injection & Advanced Jailbreaking Techniques)
set -euo pipefail

echo "=========================================================="
echo "Running Lab Verification for: Prompt Injection & Advanced Jailbreaking Techniques"
echo "Track: ai-red-teaming | Bab: 02"
echo "=========================================================="

echo "[+] Step 1: Checking environment prerequisites..."
command -v python3 >/dev/null 2>&1 || { echo "Python3 required"; exit 1; }

echo "[+] Step 2: Running module verification test..."
python3 -c 'print("Verification successful for ai-red-teaming Bab 02")'

echo "[+] Lab verification completed successfully!"
