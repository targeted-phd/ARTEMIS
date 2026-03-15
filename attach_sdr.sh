#!/bin/bash
# Auto-attach RTL-SDR from WSL side using PowerShell interop
# Add to /etc/wsl.conf [boot] command, or run manually after reboot
# Usage: sudo bash attach_sdr.sh

BUSID="2-2"
POWERSHELL="/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"

# Wait for USB subsystem
sleep 5

# Try to attach via PowerShell interop
if command -v "$POWERSHELL" &>/dev/null; then
    "$POWERSHELL" -Command "usbipd attach --wsl --busid $BUSID" 2>/dev/null
    sleep 2
fi

# Verify
if rtl_test -t 2>&1 | grep -q "Found"; then
    echo "RTL-SDR attached successfully"
else
    echo "RTL-SDR not found — run from Windows: usbipd attach --wsl --busid $BUSID"
fi
