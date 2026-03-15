# Orange Pi CM4 v1.4 -- ARTEMIS Remote Sentinel Station Setup Guide

## Hardware Reference

### Orange Pi CM4 v1.4 Core Module Specifications

| Spec             | Detail                                                       |
|------------------|--------------------------------------------------------------|
| SoC              | Rockchip RK3566, 22nm process                                |
| CPU              | Quad-core ARM Cortex-A55, up to 1.8 GHz                      |
| GPU              | ARM Mali-G52 2EE (OpenGL ES 3.2, Vulkan 1.1, OpenCL 2.0)    |
| NPU              | 0.8 TOPS @ INT8 (RKNN, supports INT8/INT16/FP16)             |
| RAM options      | 1GB / 2GB / 4GB / 8GB LPDDR4/4X                              |
| eMMC options     | 8GB / 16GB / 32GB / 64GB / 128GB                             |
| SPI flash        | Optional 128/256 Mbit                                        |
| WiFi             | 2.4G/5G dual-band Wi-Fi 5 (802.11ac)                         |
| Bluetooth        | 5.0 with BLE                                                 |
| Connectors       | 3x 100-pin + 1x 24-pin board-to-board (to carrier board)     |
| Power            | Via carrier board, 5V                                        |
| Dimensions       | 55mm x 40mm (CM4 form factor)                                |

**IMPORTANT**: The CM4 is a compute module -- it is NOT a standalone SBC. It has
no USB ports, no Ethernet jack, no HDMI, no SD card slot on the module itself.
You MUST buy the carrier/base board separately.

### Orange Pi CM4 Base Board (REQUIRED)

| Spec             | Detail                                                       |
|------------------|--------------------------------------------------------------|
| USB 3.0          | 1x USB 3.0 Host port                                        |
| USB 2.0          | 3x USB 2.0 Host ports                                       |
| Ethernet         | 1x Gigabit RJ45 (10/100/1000 Mbps)                          |
| HDMI             | 1x HDMI 2.0 (up to 4K@60Hz)                                 |
| M.2 slot         | M.2 M-Key (PCIe 2.0 x1) -- for NVMe SSD                     |
| MicroSD          | TF card slot                                                 |
| Audio            | 3.5mm headphone jack                                         |
| GPIO             | 40-pin header (Raspberry Pi compatible pinout)               |
| Display          | MIPI DSI, eDP                                                |
| Camera           | MIPI CSI                                                     |
| Power input      | USB-C 5V/3A (15W max)                                        |
| Dimensions       | ~90mm x 65mm                                                 |

### What to Buy -- Complete Shopping List

| Item                                     | Approx. Price | Notes                              |
|------------------------------------------|---------------|-------------------------------------|
| Orange Pi CM4 4G32G (4GB RAM, 32GB eMMC) | $35-45        | Minimum viable. 8G64G better.       |
| Orange Pi CM4 Base Board                 | $20-30        | Non-negotiable, provides all IO     |
| RTL-SDR Blog V3 or V4 dongle            | $25-35        | V4 preferred (better filtering)     |
| USB-C 5V/3A power supply                | $10-15        | Quality matters for 24/7 operation  |
| MicroSD card 32GB+ (Class 10 / A1)      | $8-12         | For initial OS boot                 |
| Ethernet cable (Cat5e+)                  | $5            | Wired preferred over WiFi for 24/7  |
| Small heatsink (optional)               | $3-5          | Recommended for continuous operation |
| Short USB extension cable               | $3            | Reduce stress on USB port           |

**Total: approximately $110-150** for a complete remote monitoring node.

**Recommended config**: 8GB RAM / 64GB eMMC ($50-60 for the module). The extra
RAM helps when numpy processes large IQ buffers, and eMMC provides faster/more
reliable storage than SD card for log writes.


## Power and Thermal Considerations for 24/7 Operation

### Power Consumption (RK3566-based boards, measured)

| State           | Power Draw      |
|-----------------|-----------------|
| Idle            | ~1.8W           |
| Normal load     | ~2.5W (500mA)   |
| Peak load       | ~5.25W (1050mA) |
| Sleep/standby   | <0.03W          |

The sentinel script drives moderate CPU load (numpy FFT on IQ data every few
seconds). Expect **3-4W sustained** during monitoring. A 5V/3A (15W) supply
has ample headroom.

**RTL-SDR dongle adds ~1.5W** via USB, bringing total system power to ~5-6W.

At 6W continuous: 6W x 24h x 365 = 52.6 kWh/year ~ $6/year in electricity.

### Thermal

The RK3566 runs cool at Cortex-A55 clocks. A small passive aluminum heatsink
on the SoC is sufficient. No fan needed. Operating range is 0-70C for the SoC.
The board will throttle at ~85C but this should never happen at sentinel
workloads.


## Operating System Setup

### Recommended: Ubuntu 22.04 Server (Orange Pi Official)

The official images are the most reliable choice for this board.

**Available OS options:**
- Ubuntu 22.04 (recommended -- best package support)
- Ubuntu 20.04
- Debian 11
- Debian 12
- Orange Pi OS (Arch-based)
- Android 11 (not useful for this)

### Download

1. Go to: http://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/service-and-support/Orange-Pi-CM4-1.html
2. Download the Ubuntu 22.04 **server/minimal** image (not desktop -- no GUI needed)
3. Look for filename pattern: `Orangepi-cm4_ubuntu22.04_server_*.img.xz`

Alternative download: http://www.orangepi.org/orangepiwiki/index.php/Orange_Pi_CM4

### Flash to MicroSD Card (from your main machine)

```bash
# On your main Linux machine (the one with the SDR currently)

# Install Balena Etcher or use dd
# Option 1: Balena Etcher (GUI) -- easiest
# Option 2: dd (command line)

# Find the downloaded image
ls ~/Downloads/Orangepi-cm4*.img.xz

# Decompress if needed
xz -dk Orangepi-cm4_ubuntu22.04_server_*.img.xz

# Find your SD card device (BE CAREFUL -- wrong device = data loss)
lsblk

# Flash (replace /dev/sdX with your actual SD card device)
sudo dd if=Orangepi-cm4_ubuntu22.04_server_*.img of=/dev/sdX bs=4M status=progress conv=fsync
sync
```

### First Boot

1. Insert the flashed MicroSD into the base board's TF card slot
2. Plug the CM4 module into the base board (align connectors carefully)
3. Connect Ethernet cable to your router/switch
4. Connect USB-C power (5V/3A)
5. Wait 60-90 seconds for boot

```bash
# From your main machine, find the Orange Pi on your network
# Default hostname is usually "orangepi"
# Default credentials: orangepi / orangepi (or root / orangepi)

# Method 1: Try hostname
ssh orangepi@orangepi

# Method 2: Scan your network
nmap -sn 192.168.1.0/24    # adjust subnet to match yours
# or
arp -a | grep -i "orange\|b8:27\|dc:a6"

# Method 3: Check your router's DHCP client list
```

### Post-Boot Initial Configuration

```bash
# SSH into the Orange Pi CM4
ssh orangepi@<IP_ADDRESS>

# Change default password immediately
passwd

# Set hostname
sudo hostnamectl set-hostname artemis-remote

# Set timezone
sudo timedatectl set-timezone America/New_York  # adjust to your timezone

# Update system
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y \
    build-essential \
    cmake \
    pkg-config \
    git \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    libusb-1.0-0-dev \
    libffi-dev \
    libssl-dev \
    libblas-dev \
    liblapack-dev \
    libatlas-base-dev \
    gfortran \
    htop \
    tmux \
    curl \
    wget \
    rsync \
    usbutils \
    net-tools \
    jq

# Optional: install to eMMC for better performance (after verifying SD boot works)
# See "Installing to eMMC" section below
```

### Installing to eMMC (recommended for 24/7 reliability)

SD cards degrade under constant writes. The onboard eMMC is much more reliable.

```bash
# After booting from SD card successfully, copy the image to eMMC

# Check eMMC is visible
lsblk
# Should show mmcblk0 (SD card) and mmcblk1 (eMMC) or similar

# Clone running system to eMMC
sudo dd bs=4M if=/dev/mmcblk0 of=/dev/mmcblk1 status=progress
sync

# Shut down
sudo poweroff

# Remove the SD card, then power on -- it will boot from eMMC
```


## RTL-SDR Driver Installation

The RTL-SDR uses the rtl-sdr/librtlsdr driver which works perfectly on ARM
aarch64 Linux. The sentinel.py script calls the `rtl_sdr` command-line tool.

### Install from Package Manager (quick)

```bash
sudo apt install -y rtl-sdr librtlsdr-dev
```

### Build from Source (latest version, recommended)

```bash
cd /tmp

# Clone the osmocom rtl-sdr repo
git clone https://gitea.osmocom.org/sdr/rtl-sdr.git
cd rtl-sdr

# Build
mkdir build && cd build
cmake ../ -DINSTALL_UDEV_RULES=ON -DDETACH_KERNEL_DRIVER=ON
make -j4
sudo make install
sudo ldconfig

# Install udev rules (allows non-root USB access)
sudo cp ../rtl-sdr.rules /etc/udev/rules.d/20-rtl-sdr.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### Blacklist DVB-T Kernel Module

The default kernel module interferes with RTL-SDR. Must be blacklisted.

```bash
# Create blacklist file
sudo tee /etc/modprobe.d/blacklist-rtlsdr.conf << 'EOF'
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
blacklist dvb_usb_rtl2832u
blacklist r820t
EOF

# Rebuild initramfs (might not be needed on all Orange Pi images)
sudo update-initramfs -u 2>/dev/null || true

# Reboot for blacklist to take effect
sudo reboot
```

### Verify RTL-SDR Works

```bash
# After reboot, plug in the RTL-SDR dongle to USB 3.0 port

# Check USB device is detected
lsusb
# Should show: Realtek Semiconductor Corp. RTL2838 DVB-T
# or for V4: Realtek Semiconductor Corp. RTL2838UHIDIR

# Test with rtl_test
rtl_test -t
# Should print: "Found 1 device(s)" and run successfully

# Quick capture test
rtl_sdr -f 100e6 -s 2.4e6 -n 4800000 /tmp/test.iq
ls -la /tmp/test.iq
# Should create a ~9.6MB file

# Clean up
rm /tmp/test.iq
```

**USB Port Selection**: Use the **USB 3.0 port** for the RTL-SDR. While the
RTL-SDR is USB 2.0 internally, the USB 3.0 port typically has better power
delivery and lower latency on the RK3566's USB controller. The USB 2.0 ports
work fine as fallback.


## Python Environment Setup

### Create Virtual Environment

```bash
# Create project directory
sudo mkdir -p /opt/artemis
sudo chown $(whoami):$(whoami) /opt/artemis

# Create venv with system python
python3 -m venv /opt/artemis/.venv

# Activate
source /opt/artemis/.venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel
```

### Install Python Dependencies (sentinel-only, minimal)

The remote sentinel station does NOT need the full requirements.txt (no torch,
no transformers, no Neo4j, no PDF tools). Minimal deps for sentinel.py:

```bash
# Core sentinel dependencies only
pip install numpy scipy requests

# Verify numpy BLAS linkage (important for FFT performance)
python3 -c "import numpy; numpy.show_config()"
# Should show BLAS/LAPACK linked (atlas, openblas, or blis)

# Quick FFT benchmark
python3 -c "
import numpy as np, time
z = np.random.randn(2400000) + 1j*np.random.randn(2400000)
t0 = time.time()
for _ in range(10): np.fft.fft(z)
t1 = time.time()
print(f'10x FFT of 2.4M samples: {t1-t0:.2f}s ({(t1-t0)/10*1000:.0f}ms each)')
"
# Expected: ~300-500ms per FFT on Cortex-A55 @ 1.8GHz
# This is fine -- sentinel captures take 200ms+ anyway
```

### NumPy/SciPy Performance on Cortex-A55

The Cortex-A55 has NEON SIMD and VFPv4 hardware floating point. NumPy and SciPy
use these via BLAS/LAPACK libraries (typically OpenBLAS on ARM64 Ubuntu).

**Expected performance relative to your main machine:**
- FFT (2.4M complex): ~300-500ms (vs ~50-80ms on x86_64)
- Kurtosis calculation: ~20ms
- Full analyze_iq() call: ~400-600ms total

This is adequate for sentinel monitoring. Each cycle takes 30-60s on the main
machine; expect 60-120s on the CM4. Still well within real-time requirements.

**Optimization tips:**
```bash
# Install OpenBLAS for better numpy performance
sudo apt install -y libopenblas-dev
pip install --no-binary numpy numpy  # rebuild numpy against system OpenBLAS

# Alternatively, use the pre-built ARM64 wheels (easier, good enough)
pip install numpy  # uses pre-built wheel with bundled OpenBLAS
```


## Deploy Sentinel Code

### Clone or Copy the Project

```bash
# Option 1: Git clone (if you have the repo accessible)
cd /opt/artemis
git clone <your-repo-url> rf-monitor
cd rf-monitor

# Option 2: rsync from main machine (simpler, no git needed)
# Run this on your MAIN machine:
rsync -avz --exclude='.venv' --exclude='captures*' --exclude='results' \
    --exclude='__pycache__' --exclude='.git' \
    /home/tyler/projects/rf-monitor/ \
    orangepi@<ORANGE_PI_IP>:/opt/artemis/rf-monitor/
```

### Create Required Directories

```bash
cd /opt/artemis/rf-monitor
mkdir -p results captures
```

### Test Sentinel Manually

```bash
source /opt/artemis/.venv/bin/activate
cd /opt/artemis/rf-monitor

# Short test run (5 minutes, reduced targets)
python3 sentinel.py \
    --targets 826,828,830,832,834 \
    --stare-pairs 2 \
    --sweep-start 800 \
    --sweep-stop 900 \
    --duration 300 \
    --iq-budget-mb 100 \
    --gain 28.0

# Watch for:
#   - "Found 1 device(s)" from rtl_sdr (implicit)
#   - Baseline sweep completing
#   - Stare cycles producing kurtosis values
#   - No USB errors or timeouts
```


## Network Configuration

### Option A: Tailscale VPN (Recommended)

Tailscale creates a secure mesh VPN between your machines. Already used by your
main machine (the ntfy/tag URLs use 100.x.x.x Tailscale IPs).

```bash
# Install Tailscale on the Orange Pi
curl -fsSL https://tailscale.com/install.sh | sh

# Authenticate
sudo tailscale up

# Verify connectivity to main machine
ping 100.96.113.92   # your main machine's Tailscale IP

# Note the Orange Pi's Tailscale IP for later
tailscale ip -4
```

### Option B: Direct LAN (if both machines on same network)

```bash
# Just use the LAN IP directly
ip addr show eth0
# Use this IP in the sentinel configuration
```

### Configure Sentinel for Remote Push

The sentinel already pushes alerts to ntfy and the tag server via HTTP. The
URLs are configured via environment variables:

```bash
# These should already point to your main machine
export NTFY_URL="http://100.96.113.92:8090/artemis-alerts"
export TAG_URL="http://100.96.113.92:8091/tag"

# Test connectivity
curl -s http://100.96.113.92:8090/artemis-alerts -d "CM4 test ping"
curl -s http://100.96.113.92:8091/health
```

### Automatic Data Sync (rsync cron)

Push results back to the main machine periodically:

```bash
# Generate SSH key on Orange Pi (for passwordless rsync)
ssh-keygen -t ed25519 -f ~/.ssh/artemis_sync -N ""

# Copy public key to main machine
ssh-copy-id -i ~/.ssh/artemis_sync.pub tyler@100.96.113.92

# Test rsync
rsync -avz -e "ssh -i ~/.ssh/artemis_sync" \
    /opt/artemis/rf-monitor/results/ \
    tyler@100.96.113.92:/home/tyler/projects/rf-monitor/results-remote/

# Add to crontab (sync every 15 minutes)
crontab -e
# Add this line:
# */15 * * * * rsync -avz -e "ssh -i ~/.ssh/artemis_sync" /opt/artemis/rf-monitor/results/ tyler@100.96.113.92:/home/tyler/projects/rf-monitor/results-remote/ >> /opt/artemis/sync.log 2>&1
```


## Systemd Service Configuration

### Sentinel Service

```bash
sudo tee /etc/systemd/system/artemis-sentinel.service << 'EOF'
[Unit]
Description=ARTEMIS RF Sentinel Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=orangepi
Group=orangepi
WorkingDirectory=/opt/artemis/rf-monitor
Environment=RESULTS_DIR=/opt/artemis/rf-monitor/results
Environment=IQ_DUMP_DIR=/opt/artemis/rf-monitor/captures
Environment=CHECKPOINT_FILE=/opt/artemis/rf-monitor/results/sentinel_checkpoint.json
Environment=NTFY_URL=http://100.96.113.92:8090/artemis-alerts
Environment=TAG_URL=http://100.96.113.92:8091/tag

ExecStart=/opt/artemis/.venv/bin/python3 /opt/artemis/rf-monitor/sentinel.py \
    --targets 622,624,628,630,632,634,636,826,828,830,832,834,878 \
    --sweep-start 50 \
    --sweep-stop 1000 \
    --sweep-step 6 \
    --gain 28.0 \
    --stare-dwell 200 \
    --sweep-dwell 100 \
    --stare-pairs 5 \
    --duration 604800 \
    --iq-budget-mb 10000

# Auto-restart on failure, but wait 30s to avoid USB thrashing
Restart=on-failure
RestartSec=30

# Resource limits
LimitNOFILE=4096
Nice=5

# Logging
StandardOutput=append:/opt/artemis/rf-monitor/results/sentinel_stdout.log
StandardError=append:/opt/artemis/rf-monitor/results/sentinel_stderr.log

[Install]
WantedBy=multi-user.target
EOF
```

### Log Rotation for stdout/stderr

```bash
sudo tee /etc/logrotate.d/artemis << 'EOF'
/opt/artemis/rf-monitor/results/sentinel_stdout.log
/opt/artemis/rf-monitor/results/sentinel_stderr.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    copytruncate
}
EOF
```

### Enable and Start

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable artemis-sentinel

# Start now
sudo systemctl start artemis-sentinel

# Check status
sudo systemctl status artemis-sentinel

# View live logs
journalctl -u artemis-sentinel -f

# Or tail the stdout log
tail -f /opt/artemis/rf-monitor/results/sentinel_stdout.log
```

### Watchdog Script (belt-and-suspenders)

```bash
sudo tee /opt/artemis/watchdog.sh << 'WATCHDOG'
#!/bin/bash
# ARTEMIS watchdog -- restart sentinel if it dies, check USB dongle
LOG=/opt/artemis/watchdog.log

if ! systemctl is-active --quiet artemis-sentinel; then
    echo "$(date): sentinel not running, restarting..." >> "$LOG"

    # Check if RTL-SDR dongle is present
    if ! lsusb | grep -qi "realtek"; then
        echo "$(date): RTL-SDR dongle NOT detected! Check USB." >> "$LOG"
        # Try USB reset
        for dev in /sys/bus/usb/devices/*/authorized; do
            echo 0 | sudo tee "$dev" > /dev/null 2>&1
            sleep 1
            echo 1 | sudo tee "$dev" > /dev/null 2>&1
        done
        sleep 5
    fi

    sudo systemctl restart artemis-sentinel
    echo "$(date): sentinel restarted" >> "$LOG"
fi

# Check disk space
AVAIL=$(df /opt/artemis --output=avail | tail -1)
if [ "$AVAIL" -lt 1048576 ]; then  # < 1GB
    echo "$(date): LOW DISK: ${AVAIL}KB free" >> "$LOG"
    # Prune old IQ captures
    find /opt/artemis/rf-monitor/captures -name "*.iq" -mtime +2 -delete
fi
WATCHDOG

chmod +x /opt/artemis/watchdog.sh

# Run watchdog every 5 minutes via cron
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/artemis/watchdog.sh") | crontab -
```


## NPU Capabilities (RK3566 RKNN)

The RK3566 has a 0.8 TOPS NPU. While modest, it can run lightweight ML models
for on-device RF classification -- potentially replacing the scipy kurtosis
checks with a trained neural network.

### NPU Specs

- Performance: 0.8 TOPS @ INT8, supports INT8/INT16/FP16
- Supported ops: convolution, depthwise separable conv, deconvolution,
  dilated conv, fully connected, pooling, LayerNorm
- Lossless weight compression for INT8/INT16/FP16
- Pre-processing merge, channel quantization, zero-skipping

### RKNN Toolkit Setup (for future ML deployment)

The workflow is: train model on your main machine (PyTorch/ONNX), convert to
RKNN format, deploy to Orange Pi CM4.

```bash
# ON YOUR MAIN MACHINE (x86_64) -- model conversion
pip install rknn-toolkit2

# Convert a trained ONNX model to RKNN
python3 << 'PYEOF'
from rknn.api import RKNN
rknn = RKNN()
rknn.config(target_platform='rk3566')
rknn.load_onnx(model='rf_classifier.onnx')
rknn.build(do_quantization=True, dataset='calibration_data.txt')
rknn.export_rknn('rf_classifier.rknn')
PYEOF

# ON THE ORANGE PI CM4 -- runtime inference
# Install RKNN Lite (ARM runtime, smaller than full toolkit)
pip install rknnlite2

# Or install from the Rockchip SDK:
# https://github.com/airockchip/rknn-toolkit2
```

**Practical NPU use case for ARTEMIS**: Train a small 1D-CNN or MLP on the
ml_master_dataset.json (pulse features -> anomaly classification), quantize to
INT8, deploy via RKNN. Could run inference on every IQ capture in <10ms instead
of the current scipy-based analysis. Good Phase 4 project.


## WiFi Setup (if Ethernet is not available)

WiFi is built into the CM4 module. For a stationary 24/7 monitor, Ethernet is
preferred (lower latency, more reliable). But WiFi works fine for data push.

```bash
# List available networks
sudo nmcli dev wifi list

# Connect to WiFi
sudo nmcli dev wifi connect "YOUR_SSID" password "YOUR_PASSWORD"

# Verify connection
ip addr show wlan0
ping -c 3 google.com

# Set WiFi to auto-reconnect
sudo nmcli con modify "YOUR_SSID" connection.autoconnect yes
```


## Storage Considerations

| Storage Type | Speed        | Reliability | Best For                          |
|-------------|--------------|-------------|-----------------------------------|
| MicroSD     | ~25 MB/s     | Low (wears) | Initial boot only                 |
| eMMC        | ~150 MB/s    | High        | OS + logs (recommended primary)   |
| NVMe (M.2) | ~400 MB/s*   | High        | IQ capture bulk storage           |

*PCIe 2.0 x1 limits NVMe to ~400 MB/s max, but still much faster than eMMC.

For a remote sentinel storing IQ captures, a cheap 128GB or 256GB NVMe SSD in
the M.2 M-Key slot is excellent for the captures directory. Mount it separately:

```bash
# Check if NVMe is detected
lsblk
# Should show nvme0n1

# Partition and format
sudo parted /dev/nvme0n1 mklabel gpt
sudo parted /dev/nvme0n1 mkpart primary ext4 0% 100%
sudo mkfs.ext4 /dev/nvme0n1p1

# Mount
sudo mkdir -p /mnt/captures
sudo mount /dev/nvme0n1p1 /mnt/captures
sudo chown orangepi:orangepi /mnt/captures

# Add to fstab for auto-mount
echo '/dev/nvme0n1p1 /mnt/captures ext4 defaults,noatime 0 2' | sudo tee -a /etc/fstab

# Update sentinel service to use NVMe for captures
# Change IQ_DUMP_DIR in the systemd unit to /mnt/captures
```


## Complete Setup Checklist

```
[ ] Hardware assembled (CM4 module + base board)
[ ] RTL-SDR dongle in hand
[ ] USB-C 5V/3A power supply
[ ] MicroSD card flashed with Ubuntu 22.04 server
[ ] First boot successful, SSH working
[ ] Password changed, hostname set
[ ] System updated (apt upgrade)
[ ] RTL-SDR drivers installed (rtl_sdr works)
[ ] DVB-T kernel modules blacklisted
[ ] Python venv created with numpy, scipy, requests
[ ] Sentinel code deployed to /opt/artemis/rf-monitor
[ ] RTL-SDR test capture successful
[ ] Sentinel manual test run successful (5 min)
[ ] Network configured (Tailscale or LAN)
[ ] Connectivity to main machine verified (ntfy, tag server)
[ ] Systemd service created and enabled
[ ] Watchdog cron installed
[ ] Data sync cron installed (rsync every 15 min)
[ ] Log rotation configured
[ ] (Optional) OS installed to eMMC
[ ] (Optional) NVMe SSD installed for captures
[ ] (Optional) Heatsink attached
```


## Troubleshooting

### RTL-SDR not detected
```bash
# Check USB
lsusb | grep -i realtek
# If nothing: try different USB port, check cable, check power supply

# Check kernel module conflict
lsmod | grep dvb
# If dvb_usb_rtl28xxu is loaded, the blacklist didn't work
sudo rmmod dvb_usb_rtl28xxu
sudo rmmod rtl2832
```

### USB errors / timeouts during capture
```bash
# Reduce sample rate in sentinel.py if USB bandwidth is an issue
# The default 2.4 MSPS should work fine on USB 3.0
# Try USB 2.0 port if USB 3.0 has issues (rare but possible)

# Check for USB power issues
dmesg | grep -i "usb\|over-current"
# If over-current: use a powered USB hub
```

### numpy slow (no BLAS)
```bash
# Check BLAS linkage
python3 -c "import numpy; numpy.show_config()"
# If no BLAS shown:
sudo apt install libopenblas-dev
pip install --force-reinstall --no-binary numpy numpy
```

### Sentinel dies after hours
```bash
# Check if it's a memory issue (4GB might be tight with large IQ buffers)
free -h
# If OOM: reduce --stare-pairs or --iq-budget-mb

# Check systemd logs
journalctl -u artemis-sentinel --since "1 hour ago" --no-pager

# The watchdog cron should auto-restart it
cat /opt/artemis/watchdog.log
```

### No network after reboot
```bash
# Check Ethernet
ip link show eth0
sudo dhclient eth0

# Check WiFi
nmcli dev status
sudo nmcli dev wifi connect "SSID" password "PASS"

# Check Tailscale
sudo tailscale status
sudo tailscale up
```


## Architecture: Main Machine + Remote Sentinel

```
 REMOTE SITE                          MAIN MACHINE (tyler's desktop)
 ┌─────────────────────┐              ┌──────────────────────────────┐
 │  Orange Pi CM4       │              │  WSL2 / Ubuntu               │
 │  ┌───────────────┐  │              │  ┌────────────────────────┐  │
 │  │  sentinel.py   │──┼── ntfy ────>│  │  ntfy server (:8090)   │  │
 │  │  (stare+sweep) │  │   alerts    │  └────────────────────────┘  │
 │  └───────┬───────┘  │              │  ┌────────────────────────┐  │
 │          │ IQ data   │              │  │  tag_server.py (:8091) │  │
 │  ┌───────┴───────┐  │              │  └────────────────────────┘  │
 │  │  results/      │──┼── rsync ──> │  ┌────────────────────────┐  │
 │  │  sentinel_*.   │  │   every     │  │  results-remote/       │  │
 │  │  jsonl         │  │   15 min    │  │  (merged analysis)     │  │
 │  └───────────────┘  │              │  └────────────────────────┘  │
 │  ┌───────────────┐  │              │  ┌────────────────────────┐  │
 │  │  RTL-SDR V3/4 │  │              │  │  RTL-SDR (local)       │  │
 │  │  (USB dongle)  │  │              │  │  + local sentinel.py   │  │
 │  └───────────────┘  │              │  └────────────────────────┘  │
 │                      │              │                              │
 │  Tailscale VPN ──────┼──────────── │  Tailscale VPN               │
 │  100.x.x.x          │              │  100.96.113.92               │
 └─────────────────────┘              └──────────────────────────────┘
        ~6W power                              Main analysis
        Runs 24/7                              ML training
        Headless                               Dashboard
```

Two sentinels at different locations = spatial diversity. If both stations
detect the same frequency anomalies simultaneously, that's strong evidence
of a real broadcast rather than local interference. If only one detects it,
you know the source is local to that site.
