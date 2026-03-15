# Run this from Windows PowerShell to auto-attach RTL-SDR to WSL
# Install as scheduled task: runs on login + every 5 minutes
# PowerShell: schtasks /create /tn "USBIPDAutoAttach" /tr "powershell -ExecutionPolicy Bypass -File C:\Users\Tyler\attach_sdr.ps1" /sc onlogon /rl highest

$busid = "2-2"

# Check if already attached
$status = usbipd list 2>$null | Select-String $busid
if ($status -match "Attached") {
    exit 0
}

# Attach to WSL
usbipd attach --wsl --busid $busid 2>$null
