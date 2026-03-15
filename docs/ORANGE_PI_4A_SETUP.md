# ARTEMIS RF Monitoring Station: Orange Pi 4A Setup Guide

Complete guide to deploying the ARTEMIS sentinel.py RF monitoring system on an
Orange Pi 4A single-board computer with RTL-SDR.

---

## 1. Hardware Specifications — Orange Pi 4A

| Component | Specification |
|-----------|--------------|
| **SoC** | Allwinner T527 |
| **CPU** | 8x ARM Cortex-A55 @ 1.8 GHz |
| **Co-processor** | T-Head E906 RISC-V MCU |
| **DSP** | HiFi4 DSP |
| **GPU** | Mali-G57 MC1 (Valhall architecture) |
| **NPU** | Vivante VIP9000 — 2 TOPS (INT8/INT16) |
| **RAM** | 2 GB or 4 GB LPDDR4/4X (**get the 4 GB model**) |
| **Storage** | microSD (up to 128 GB), optional eMMC (16-128 GB), M.2 M-Key PCIe 2.0 NVMe (2280) |
| **USB** | 4x USB 2.0 Host |
| **Ethernet** | Gigabit Ethernet (RJ45) |
| **WiFi** | WiFi 5 (802.11ac) 2.4/5 GHz |
| **Bluetooth** | BT 5.0 + BLE |
| **Video Out** | HDMI 2.0 (4K@60), MIPI-DSI (4-lane), eDP 1.3 |
| **GPIO** | 40-pin header (Raspberry Pi compatible: GPIO, UART, I2C, SPI, PWM) |
| **Power** | USB-C (5V input) |
| **Idle Power** | ~4.6 W |
| **Form Factor** | Credit-card size (~85x56 mm, Raspberry Pi footprint) |
| **OS Support** | Ubuntu, Debian, Android 13, Armbian (community) |
| **Price** | ~$47 (2 GB) / ~$53 (4 GB) |

### Performance Context

The Orange Pi 4A performs between a Raspberry Pi 4 and a Raspberry Pi 5 in
general benchmarks (Tom's Hardware testing). For our use case — running
sentinel.py with 2.4 Msps IQ capture and numpy/scipy analysis — the 8-core
A55 cluster at 1.8 GHz is more than adequate. The Pi 4 handles this workload,
and the 4A has more cores and comparable per-core performance.

### Why the 4A for ARTEMIS

- **4x USB 2.0 ports**: RTL-SDR needs USB 2.0; the 4A has four dedicated ports
  (not shared with Ethernet like older Orange Pi models)
- **2 TOPS NPU**: On-device ML inference for anomaly classification without
  needing the GTX 1080 desktop
- **Gigabit Ethernet + WiFi 5**: Reliable data push to central server
- **NVMe slot**: Fast local storage for IQ captures
- **Low power**: ~5W idle, ~8W under load — runs 24/7 on a USB-C adapter
- **GPIO**: Future expansion (temperature sensor, relay for antenna switching)

---

## 2. Shopping List

| Item | Notes | Approx. Price |
|------|-------|---------------|
| Orange Pi 4A 4GB | **Must be 4 GB model** for scipy/ML workloads | $53 |
| 32-128 GB microSD (A2 rated) | Samsung EVO Select or SanDisk Extreme | $10-20 |
| RTL-SDR Blog V4 | USB dongle + antenna kit | $30 |
| USB-C power supply 5V/4A (20W) | Geekworm or CanaKit brand, must be 4A+ | $12 |
| Ethernet cable (Cat6) | For reliable data push; WiFi is backup | $5 |
| Heatsink + fan (optional) | Passive heatsink is fine for our workload | $5-10 |
| **Optional: NVMe SSD** | 128-256 GB 2280 M.2 for IQ captures | $20-30 |
| **Optional: eMMC module** | 32-64 GB for faster OS boot than microSD | $15-25 |

### Optional Extras for Advanced Deployment

| Item | Notes | Approx. Price |
|------|-------|---------------|
| UPS HAT (Geekworm X1200/X1202) | 18650 battery backup, auto-failover | $25-35 |
| 18650 batteries (2-4x) | Samsung 30Q or Sony VTC6 | $10-20 |
| Sixfab IP65 Outdoor Enclosure | RF-transparent ABS, cable grommets | $40 |
| SMA extension cable (3m) | Route antenna outside enclosure | $10 |
| USB cable (short, ferrite core) | Reduce USB noise for RTL-SDR | $5 |

---

## 3. OS Installation

### 3.1 Recommended: Official Orange Pi Ubuntu/Debian Image

The official Orange Pi images have the best hardware support (NPU drivers,
GPU acceleration, WiFi firmware). Use the **Ubuntu server** or **Debian server**
image for headless operation.

**Download**: http://www.orangepi.org/orangepiwiki/index.php/Orange_Pi_4A
(navigate to "Images Download" section)

```bash
# On your desktop (Linux/Mac/WSL):

# 1. Download the server image (not desktop — no GUI needed)
#    Look for: Orangepi4a_1.0.0_ubuntu_noble_server_linux6.6.36.7z
#    or:       Orangepi4a_1.0.0_debian_bookworm_server_linux6.6.36.7z

# 2. Extract the image
7z x Orangepi4a_*.7z
# or: xz -d Orangepi4a_*.img.xz

# 3. Flash to microSD card
#    Find your SD card device (BE CAREFUL — wrong device = data loss):
lsblk
#    Usually /dev/sdb or /dev/mmcblk0

# Flash (replace /dev/sdX with your SD card):
sudo dd if=Orangepi4a_*.img of=/dev/sdX bs=4M status=progress conv=fsync
sync
```

### 3.2 Alternative: Armbian

Armbian has community support for the T527 (forum thread active since 2024).
Check https://www.armbian.com/download/ for "Orange Pi 4A" availability.
Armbian images may have better mainline kernel support but potentially
incomplete NPU drivers.

### 3.3 First Boot (Headless)

```bash
# 1. Insert microSD into the Orange Pi 4A
# 2. Connect Ethernet cable to your router
# 3. Connect RTL-SDR USB dongle
# 4. Connect USB-C power — board boots automatically

# 5. Find the IP address:
#    Check your router's DHCP client list, or:
nmap -sn 192.168.1.0/24 | grep -i orange
#    or from another Linux machine:
arp-scan --localnet | grep -i orange

# 6. SSH in (default credentials vary by image):
#    Orange Pi official images: root / orangepi
#    Armbian: root / 1234 (prompts for new password on first login)
ssh root@<IP_ADDRESS>

# 7. Change default password immediately
passwd

# 8. Create a non-root user
adduser tyler
usermod -aG sudo,plugdev,dialout tyler

# 9. Set hostname
hostnamectl set-hostname artemis-opi
```

---

## 4. System Setup

Run all commands below as root (or with sudo) on the Orange Pi.

### 4.1 System Update

```bash
apt update && apt upgrade -y
apt install -y \
    build-essential \
    git \
    curl \
    wget \
    htop \
    tmux \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    python3-numpy \
    python3-scipy \
    cmake \
    pkg-config \
    libusb-1.0-0-dev \
    libfftw3-dev \
    usbutils \
    net-tools \
    jq
```

### 4.2 Set Performance CPU Governor

Important for consistent IQ capture timing. Without this, the CPU may clock
down during captures and cause sample drops.

```bash
# Install cpufrequtils
apt install -y cpufrequtils

# Set performance mode (all 8 cores at max 1.8 GHz)
echo 'GOVERNOR="performance"' | tee /etc/default/cpufrequtils
systemctl restart cpufrequtils

# Verify
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
# Should show "performance" for all 8 cores
```

### 4.3 Set Timezone

```bash
timedatectl set-timezone America/Chicago
# Verify:
date
```

### 4.4 Configure Static IP (Optional but Recommended)

```bash
# Edit netplan config (Ubuntu) or /etc/network/interfaces (Debian)
# Ubuntu with netplan:
cat > /etc/netplan/01-static.yaml << 'EOF'
network:
  version: 2
  renderer: networkd
  ethernets:
    eth0:
      dhcp4: no
      addresses:
        - 192.168.1.50/24
      routes:
        - to: default
          via: 192.168.1.1
      nameservers:
        addresses:
          - 1.1.1.1
          - 8.8.8.8
EOF

netplan apply
```

---

## 5. RTL-SDR Driver Installation

### 5.1 Install librtlsdr from Source (Recommended)

The ARM64 package repos sometimes have outdated versions. Build from source
for best compatibility with RTL-SDR Blog V4.

```bash
# Blacklist the kernel DVB-T driver (conflicts with SDR mode)
echo 'blacklist dvb_usb_rtl28xxu' | tee /etc/modprobe.d/blacklist-rtlsdr.conf
echo 'blacklist rtl2832' >> /etc/modprobe.d/blacklist-rtlsdr.conf
echo 'blacklist rtl2830' >> /etc/modprobe.d/blacklist-rtlsdr.conf

# Build librtlsdr
cd /opt
git clone https://github.com/rtlsdrblog/rtl-sdr-blog.git
cd rtl-sdr-blog
mkdir build && cd build
cmake .. -DINSTALL_UDEV_RULES=ON -DDETACH_KERNEL_DRIVER=ON
make -j$(nproc)
make install
ldconfig

# The build installs udev rules to /etc/udev/rules.d/rtl-sdr.rules
# If not, create manually:
cat > /etc/udev/rules.d/10-rtl-sdr.rules << 'EOF'
# RTL-SDR Blog V4 and generic RTL2832U
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2832", MODE="0666", GROUP="plugdev"
EOF

# Reload udev rules
udevadm control --reload-rules
udevadm trigger

# Reboot to apply blacklist
reboot
```

### 5.2 Verify RTL-SDR Detection

```bash
# After reboot, SSH back in

# Check USB device is visible
lsusb | grep -i realtek
# Should show: Bus 00x Device 00x: ID 0bda:2838 Realtek Semiconductor Corp. RTL2838 DVB-T

# Run hardware test
rtl_test -t
# Should show: "Found 1 device(s):" and pass the test

# Quick capture test (10ms at 100 MHz)
rtl_sdr -f 100000000 -s 2400000 -n 480000 /tmp/test.iq
ls -la /tmp/test.iq
# Should be 960000 bytes (480000 samples x 2 bytes per IQ pair)

# Non-root user test (important for running as tyler, not root):
su - tyler
rtl_test -t
# If this fails with "Permission denied", check udev rules above
```

### 5.3 Known Issues: RTL-SDR on ARM SBCs

**USB bandwidth sharing**: Unlike the Raspberry Pi 3 (where Ethernet and USB
shared a single bus), the Orange Pi 4A has dedicated USB and Ethernet
controllers. This eliminates the classic "USB bandwidth starvation" problem.

**Sample rate ceiling**: At 2.4 Msps, each IQ sample is 2 bytes, so the data
rate is 4.8 MB/s. USB 2.0 High Speed supports 480 Mbps (60 MB/s), so we are
well within limits. The A55 cores can handle the numpy FFT/analysis at this
rate — the Raspberry Pi 4 (also Cortex-A72, similar IPC) handles it fine.

**Thermal throttling**: Under sustained capture, the T527 may thermal throttle
if not cooled. A passive heatsink is sufficient; an active fan is overkill for
our workload. Monitor with:
```bash
cat /sys/class/thermal/thermal_zone0/temp
# Divide by 1000 for degrees C. Keep below 80C.
```

**USB cable quality**: Use a short, high-quality USB cable (ideally with
ferrite cores) between the RTL-SDR and the Orange Pi. Long or cheap cables
cause sample drops at 2.4 Msps.

---

## 6. Python Environment Setup

### 6.1 Create Virtual Environment

```bash
# Switch to your non-root user
su - tyler
mkdir -p ~/projects
cd ~/projects

# Clone the ARTEMIS repo
git clone <your-repo-url> rf-monitor
cd rf-monitor

# Create venv with system numpy/scipy (pre-compiled ARM64 wheels)
python3 -m venv .venv --system-site-packages

# Activate
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel
```

### 6.2 Install Dependencies

The full requirements.txt includes packages not needed on the edge station
(torch, transformers, Neo4j, grobid, docling). Install only what sentinel.py
and the dashboard need:

```bash
# Create edge-specific requirements
cat > requirements-edge.txt << 'EOF'
# ARTEMIS Edge Station — Orange Pi 4A
# Core scientific (may already be installed via system packages)
numpy
scipy
matplotlib
scikit-learn

# Data handling
pandas
jsonlines

# HTTP / networking
requests

# Utilities
tqdm
psutil
python-dateutil

# RTL-SDR Python binding (optional — sentinel.py uses subprocess to rtl_sdr)
# pyrtlsdr
EOF

pip install -r requirements-edge.txt
```

### 6.3 Verify Python Stack

```bash
python3 -c "
import numpy as np
from scipy import stats
print(f'numpy {np.__version__}')
print(f'scipy version OK')

# Quick FFT benchmark (simulates sentinel.py workload)
import time
samples = 2_400_000  # 1 second at 2.4 Msps
z = np.random.randn(samples) + 1j * np.random.randn(samples)
t0 = time.time()
for _ in range(10):
    Z = np.fft.fft(z)
elapsed = time.time() - t0
print(f'10x FFT of {samples} samples: {elapsed:.2f}s ({elapsed/10*1000:.0f}ms per FFT)')
print(f'Must be < 200ms for real-time. Result: {\"PASS\" if elapsed/10 < 0.2 else \"WARN - may need optimization\"} ')
"
```

Expected output: each FFT should take 50-150ms on the A55 cluster. Our
sentinel.py capture dwell is 200ms, and we only FFT the captured window
(~576,000 samples at 200ms dwell), so this is well within budget.

---

## 7. Deploy ARTEMIS Sentinel

### 7.1 Configuration for Edge Deployment

The sentinel.py uses environment variables for configuration. Create an
environment file:

```bash
cat > ~/projects/rf-monitor/.env << 'EOF'
# ARTEMIS Edge Station Configuration
RESULTS_DIR=/home/tyler/projects/rf-monitor/results
IQ_DUMP_DIR=/home/tyler/projects/rf-monitor/captures
CHECKPOINT_FILE=/home/tyler/projects/rf-monitor/results/sentinel_checkpoint.json

# Central server (your desktop running ntfy + tag_server)
# Update these to your actual Tailscale or LAN IPs
NTFY_URL=http://100.96.113.92:8090/artemis-alerts
TAG_URL=http://100.96.113.92:8091/tag
EOF
```

### 7.2 Test Run

```bash
cd ~/projects/rf-monitor
source .venv/bin/activate
source .env

# Short test run — 5 minutes, reduced sweep
python3 sentinel.py \
    --targets 622,624,628,630,632,634,636,826,828,830,832,834,878 \
    --duration 300 \
    --stare-dwell 200 \
    --sweep-dwell 100 \
    --stare-pairs 3 \
    --gain 28 \
    --iq-budget-mb 100

# Verify output
ls -la results/sentinel_*.jsonl
cat results/sentinel_checkpoint.json | python3 -m json.tool
```

### 7.3 systemd Service (Auto-Start on Boot)

```bash
sudo cat > /etc/systemd/system/artemis-sentinel.service << 'EOF'
[Unit]
Description=ARTEMIS RF Sentinel Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=tyler
Group=tyler
WorkingDirectory=/home/tyler/projects/rf-monitor
EnvironmentFile=/home/tyler/projects/rf-monitor/.env
ExecStart=/home/tyler/projects/rf-monitor/.venv/bin/python3 sentinel.py \
    --targets 622,624,628,630,632,634,636,826,828,830,832,834,878 \
    --duration 86400 \
    --stare-dwell 200 \
    --sweep-dwell 100 \
    --stare-pairs 5 \
    --gain 28 \
    --iq-budget-mb 50000
Restart=on-failure
RestartSec=30
StandardOutput=append:/home/tyler/projects/rf-monitor/results/sentinel_stdout.log
StandardError=append:/home/tyler/projects/rf-monitor/results/sentinel_stderr.log

# Watchdog: restart if unresponsive for 5 minutes
WatchdogSec=300

# Resource limits
LimitNOFILE=65535
Nice=-5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable artemis-sentinel
sudo systemctl start artemis-sentinel

# Check status
sudo systemctl status artemis-sentinel
sudo journalctl -u artemis-sentinel -f
```

### 7.4 Dashboard Service (Optional — for Local Monitoring)

```bash
sudo cat > /etc/systemd/system/artemis-dashboard.service << 'EOF'
[Unit]
Description=ARTEMIS Dashboard
After=network-online.target

[Service]
Type=simple
User=tyler
Group=tyler
WorkingDirectory=/home/tyler/projects/rf-monitor
EnvironmentFile=/home/tyler/projects/rf-monitor/.env
Environment=DASH_PORT=8080
ExecStart=/home/tyler/projects/rf-monitor/.venv/bin/python3 dashboard.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable artemis-dashboard
sudo systemctl start artemis-dashboard

# Access from your network: http://<orange-pi-ip>:8080
```

Note: dashboard.py currently binds to 127.0.0.1. For remote access, either:
- Modify the bind address to 0.0.0.0 (LAN only, not internet-exposed)
- Use SSH tunnel: `ssh -L 8080:localhost:8080 tyler@<orange-pi-ip>`
- Use Tailscale (recommended)

### 7.5 Tag Server Service

```bash
sudo cat > /etc/systemd/system/artemis-tags.service << 'EOF'
[Unit]
Description=ARTEMIS Symptom Tag Server
After=network-online.target

[Service]
Type=simple
User=tyler
Group=tyler
WorkingDirectory=/home/tyler/projects/rf-monitor
EnvironmentFile=/home/tyler/projects/rf-monitor/.env
ExecStart=/home/tyler/projects/rf-monitor/.venv/bin/python3 tag_server.py --host 0.0.0.0
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable artemis-tags
sudo systemctl start artemis-tags
```

---

## 8. Network Configuration

### 8.1 Tailscale (Recommended for Secure Remote Access)

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Authenticate
sudo tailscale up

# Note the Tailscale IP (100.x.x.x)
tailscale ip -4

# Update .env with this Orange Pi's Tailscale IP for the tag server
# and the desktop's Tailscale IP for ntfy
```

### 8.2 Data Push to Central Server

#### Option A: Git Auto-Push (Same as Desktop)

```bash
# Set up SSH key for GitHub
ssh-keygen -t ed25519 -C "artemis-opi" -f ~/.ssh/github-artemis
# Add the public key to your GitHub repo as a deploy key

# Configure git
cd ~/projects/rf-monitor
git remote set-url origin git@github.com:your-user/rf-monitor.git

# Install the same autopush cron job
crontab -e
# Add:
# 0 * * * * /home/tyler/projects/rf-monitor/autopush.sh >> /home/tyler/projects/rf-monitor/results/autopush.log 2>&1
```

#### Option B: rsync to Central Server

```bash
# Push results every 15 minutes
cat > ~/sync_results.sh << 'SCRIPT'
#!/bin/bash
rsync -avz --progress \
    /home/tyler/projects/rf-monitor/results/ \
    tyler@desktop-tailscale-ip:/home/tyler/projects/rf-monitor/results-opi/
SCRIPT
chmod +x ~/sync_results.sh

# Cron job
crontab -e
# */15 * * * * /home/tyler/sync_results.sh >> /home/tyler/sync.log 2>&1
```

#### Option C: MQTT/HTTP Push (Real-Time)

For real-time data forwarding, modify sentinel.py to POST each cycle's JSON
to your central server. The ntfy push mechanism already does this for alerts.

### 8.3 WiFi Configuration (If No Ethernet)

```bash
# List available networks
nmcli device wifi list

# Connect
nmcli device wifi connect "YourSSID" password "YourPassword"

# Verify
ip addr show wlan0
ping -c 3 8.8.8.8
```

---

## 9. NPU Setup — On-Device ML Inference

The Allwinner T527 NPU uses the Vivante VIP9000 architecture with the
ACUITY Toolkit for model conversion and the awnn runtime for on-device
inference.

### 9.1 NPU Software Stack

```
Your Desktop (x86_64)              Orange Pi 4A (ARM64)
┌────────────────────┐             ┌────────────────────┐
│ PyTorch/ONNX Model │             │                    │
│         ↓          │             │  awnn Runtime API  │
│  ACUITY Toolkit    │ ──NBG──→   │         ↓          │
│  (model convert)   │  file      │  VIP9000 NPU HW    │
│         ↓          │             │  (2 TOPS INT8)     │
│   .nb model file   │             │                    │
└────────────────────┘             └────────────────────┘
```

### 9.2 Supported Frameworks (Input)

The ACUITY Toolkit can convert models from:
- PyTorch (via ONNX export)
- ONNX
- TensorFlow / TensorFlow Lite
- Caffe
- DarkNet
- Keras

Quantization support: UINT8, INT8 (PCQ), INT16, BF16, and mixed quantization.

### 9.3 Install NPU SDK on the Orange Pi

```bash
# The official Orange Pi images should include the NPU runtime libraries.
# Verify:
ls /usr/lib/libawnn* 2>/dev/null
ls /usr/lib/libVIPlite* 2>/dev/null

# If not present, install from Orange Pi SDK:
# (Download from Orange Pi wiki → T527 SDK section)
# The key files needed:
#   /usr/lib/libawnn.so
#   /usr/lib/libVIPlite.so
#   /usr/bin/awnn_run

# Set NPU version for T527
export NPU_SW_VERSION=v1.13

# Test NPU availability
awnn_run --help 2>/dev/null && echo "NPU runtime: OK" || echo "NPU runtime: NOT INSTALLED"
```

### 9.4 Convert ARTEMIS ML Models for NPU

On your desktop, convert your scikit-learn or PyTorch models:

```bash
# 1. Export your anomaly detection model to ONNX
python3 -c "
import torch
import numpy as np

# Example: convert a simple anomaly scorer to ONNX
# Your rf_ml.py models would go here
class AnomalyScorer(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = torch.nn.Linear(15, 64)
        self.fc2 = torch.nn.Linear(64, 32)
        self.fc3 = torch.nn.Linear(32, 1)
        self.relu = torch.nn.ReLU()
        self.sigmoid = torch.nn.Sigmoid()

    def forward(self, x):
        x = self.relu(self.fc1(x))
        x = self.relu(self.fc2(x))
        return self.sigmoid(self.fc3(x))

model = AnomalyScorer()
dummy = torch.randn(1, 15)
torch.onnx.export(model, dummy, 'anomaly_scorer.onnx',
                  input_names=['features'], output_names=['score'])
print('Exported anomaly_scorer.onnx')
"

# 2. Convert ONNX to NBG using ACUITY Toolkit
#    (Install ACUITY on your desktop — Linux x86_64 only)
#    Download from: https://github.com/VeriSilicon/acuity-toolkit
#
#    pegasus import --model anomaly_scorer.onnx --framework ONNX
#    pegasus generate --target-npu-version v2 --quantize-dtype INT8
#    # Output: anomaly_scorer.nb

# 3. Copy .nb file to Orange Pi
scp anomaly_scorer.nb tyler@artemis-opi:~/projects/rf-monitor/models/
```

### 9.5 Run NPU Inference from Python

```python
# npu_inference.py — Example wrapper for awnn NPU inference
import subprocess
import numpy as np
import struct
import tempfile
import os

class NPUModel:
    """Run a converted .nb model on the Allwinner T527 NPU via awnn."""

    def __init__(self, model_path):
        self.model_path = model_path
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")

    def predict(self, features):
        """Run inference on a feature vector.
        features: numpy array of float32
        Returns: numpy array of outputs
        """
        # Write input to temp file
        with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as f:
            features.astype(np.float32).tofile(f)
            input_path = f.name

        output_path = input_path + '.out'

        try:
            # Run awnn inference
            result = subprocess.run(
                ['awnn_run', self.model_path, input_path, output_path],
                capture_output=True, timeout=5)
            if result.returncode != 0:
                raise RuntimeError(f"NPU inference failed: {result.stderr.decode()}")

            # Read output
            output = np.fromfile(output_path, dtype=np.float32)
            return output
        finally:
            os.unlink(input_path)
            if os.path.exists(output_path):
                os.unlink(output_path)
```

### 9.6 Practical NPU Strategy for ARTEMIS

For the RF monitoring use case, the most impactful NPU models are:

1. **Anomaly classifier**: Takes per-cycle features (kurtosis, PAPR, pulse
   count, EI, etc.) and outputs anomaly score. Small model (~15 inputs,
   few hidden layers) — runs in <1ms on NPU.

2. **Signal fingerprinter**: Takes FFT magnitude spectrum (e.g., 1024 bins)
   and classifies signal type. Medium model — runs in ~5ms on NPU.

3. **Pulse shape classifier**: Takes short IQ segments around detected pulses
   and classifies modulation type. This is where 2 TOPS really helps.

For initial deployment, the CPU is fast enough for the scikit-learn models
in rf_ml.py. Export to ONNX and convert to NPU only after validating the
model on desktop first.

---

## 10. Cron Jobs and Automation

```bash
# Edit crontab
crontab -e

# Add these entries:
# ──────────────────────────────────────────────────────────────────────
# Auto-push results to GitHub every hour
0 * * * * /home/tyler/projects/rf-monitor/autopush.sh >> /home/tyler/projects/rf-monitor/results/autopush.log 2>&1

# Blind symptom check-in every 30 minutes (if running tag_server locally)
*/30 * * * * /home/tyler/projects/rf-monitor/scheduled_checkin.sh >> /dev/null 2>&1

# Rebuild ML dataset after each auto-push
5 * * * * cd /home/tyler/projects/rf-monitor && bash rebuild_ml_dataset.sh >> results/rebuild_ml.log 2>&1

# Hourly integrity hash
0 * * * * cd /home/tyler/projects/rf-monitor && bash hash_timestamp.sh >> results/evidence/hourly_hashes.log 2>&1

# Health check — restart sentinel if it died
*/5 * * * * systemctl is-active --quiet artemis-sentinel || systemctl restart artemis-sentinel

# Daily log rotation — compress old sentinel logs
0 4 * * * find /home/tyler/projects/rf-monitor/results -name 'sentinel_*.jsonl' -mtime +7 -exec gzip {} \;

# Thermal monitoring — log temperature every 5 minutes
*/5 * * * * echo "$(date -Iseconds) $(cat /sys/class/thermal/thermal_zone0/temp)" >> /home/tyler/projects/rf-monitor/results/thermal.log
# ──────────────────────────────────────────────────────────────────────
```

---

## 11. Power and 24/7 Operation

### 11.1 Power Supply Requirements

The Orange Pi 4A draws ~4.6W at idle and up to ~8W under sustained load
(all 8 cores active + USB peripheral). With an RTL-SDR dongle (draws ~300mA
at 5V = 1.5W), total system power is approximately 6-10W.

**Minimum power supply**: 5V / 3A (15W) USB-C
**Recommended**: 5V / 4A (20W) USB-C — provides headroom for NVMe SSD and
USB peripherals

Recommended adapters:
- Geekworm 20W USB-C (5V/4A) — designed for SBCs
- CanaKit 3.5A USB-C — widely available
- Any USB-C PD adapter that supports 5V/3A+ profile

**Warning**: Do NOT use a phone charger. Many phone chargers only provide
5V/1A or negotiate higher voltages (9V, 12V) via USB-PD. The Orange Pi 4A
needs a stable 5V at 3-4A.

### 11.2 UPS Battery Backup

For uninterrupted monitoring during power outages:

**Option A: Dedicated SBC UPS HAT**
- Geekworm X1200 (2x 18650, 5.1V/5A output) — fits Raspberry Pi form factor,
  compatible with Orange Pi 4A via GPIO header
- Geekworm X1202 (4x 18650) — longer runtime
- Runtime estimate: 2x Samsung 30Q (3000mAh each) at 8W draw = ~3-4 hours

**Option B: USB-C Power Bank**
- Any 20W+ USB-C PD power bank works
- 10,000 mAh bank at 8W draw = ~5 hours
- 20,000 mAh = ~10 hours
- Note: Some power banks auto-shutoff with low-draw devices. Test yours.

**Option C: 12V Battery + Buck Converter**
- 12V 7Ah SLA battery + USB-C buck converter
- Runtime: ~8-10 hours
- Best for permanent outdoor installations

### 11.3 Graceful Shutdown on Power Loss

If using a UPS HAT with GPIO, configure auto-shutdown:

```bash
# Add to /etc/rc.local or a systemd service:
# Monitor GPIO pin for low-battery signal from UPS HAT
# When triggered, do graceful shutdown:
# 1. Save sentinel checkpoint
# 2. Sync filesystems
# 3. Shutdown

cat > /usr/local/bin/power_monitor.sh << 'SCRIPT'
#!/bin/bash
# Monitor UPS low-battery GPIO (adjust pin number for your UPS HAT)
GPIO_PIN=17
echo $GPIO_PIN > /sys/class/gpio/export 2>/dev/null
echo "in" > /sys/class/gpio/gpio${GPIO_PIN}/direction

while true; do
    if [ "$(cat /sys/class/gpio/gpio${GPIO_PIN}/value)" = "0" ]; then
        logger "UPS: Low battery detected, shutting down in 30s"
        sleep 30
        systemctl stop artemis-sentinel
        sync
        shutdown -h now
    fi
    sleep 10
done
SCRIPT
chmod +x /usr/local/bin/power_monitor.sh
```

---

## 12. Performance Tuning

### 12.1 IQ Processing Budget

Sentinel.py capture cycle timing on Orange Pi 4A (estimated):

| Operation | Time (estimated) |
|-----------|-----------------|
| rtl_sdr capture (200ms dwell) | ~250ms (includes USB overhead) |
| IQ demodulation + DC notch FFT | ~30-80ms |
| analyze_iq (kurtosis, pulse detect) | ~10-20ms |
| File I/O (write JSONL + IQ file) | ~5-10ms |
| **Total per frequency per dwell** | **~300-360ms** |

With 13 target frequencies, 5 stare pairs per cycle, and sweep:
- Stare phase: 13 freqs x 5 pairs x ~350ms = ~22.8 seconds
- Sweep phase: ~55 channels x ~250ms = ~13.8 seconds
- **Total cycle time: ~37 seconds** (vs ~30s on desktop)

This is well within real-time requirements. The sentinel runs continuously
with no sample backlog.

### 12.2 Memory Optimization

With 4 GB RAM, memory is tighter than the desktop. Key settings:

```bash
# Reduce swap aggressiveness (keep data in RAM)
echo 'vm.swappiness=10' | tee -a /etc/sysctl.conf
sysctl -p

# Add swap file (just in case)
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

### 12.3 Storage Strategy

For IQ captures, the microSD card is too slow and has limited write endurance.

**Best option: NVMe SSD in M.2 slot**
```bash
# After installing NVMe SSD in the M.2 slot:
lsblk  # Should show nvme0n1

# Create filesystem
mkfs.ext4 /dev/nvme0n1p1

# Mount as captures directory
mkdir -p /mnt/nvme
mount /dev/nvme0n1p1 /mnt/nvme
echo '/dev/nvme0n1p1 /mnt/nvme ext4 defaults,noatime 0 2' >> /etc/fstab

# Symlink captures directory
ln -sf /mnt/nvme/captures /home/tyler/projects/rf-monitor/captures
```

**Alternative: USB flash drive**
```bash
# For a second USB drive dedicated to captures
mount /dev/sda1 /mnt/usb
ln -sf /mnt/usb/captures /home/tyler/projects/rf-monitor/captures
```

### 12.4 Reduce IQ Budget for Edge Station

On the desktop with 925 GB available, IQ budget is 500 GB. On the edge
station, be more conservative:

```bash
# In the systemd service, set --iq-budget-mb based on available storage:
# 32 GB microSD: --iq-budget-mb 5000   (5 GB)
# 128 GB NVMe:   --iq-budget-mb 50000  (50 GB)
# 256 GB NVMe:   --iq-budget-mb 150000 (150 GB)
```

---

## 13. Outdoor Deployment

### 13.1 Weatherproof Enclosure

**Sixfab IP65 Outdoor Project Enclosure** (~$40)
- IP65 rated (dust-tight, water-jet resistant)
- RF-transparent ABS plastic (does not block WiFi or cellular)
- Cable grommets for power and antenna feed-through
- Fits Raspberry Pi form factor boards (including Orange Pi 4A)
- Mounting brackets for pole/wall mount

**Altelix NEMA 4X Enclosures** ($50-100)
- IP65/IP66 rated
- Available in various sizes
- RF transparent options available

### 13.2 Antenna Routing

```
                    ┌──────────────────┐
     Antenna        │  IP65 Enclosure  │
    (outside)       │                  │
        │           │  ┌────────────┐  │
        │           │  │ Orange Pi  │  │
   SMA cable        │  │    4A      │  │
   through ──────── │──│ [RTL-SDR]──│──│── USB-C power
   grommet          │  │            │  │    (weatherproof
        │           │  └────────────┘  │     cable gland)
        │           │                  │
        ▼           └──────────────────┘
   Antenna mount
   (pole/eave)
```

Key considerations:
- Route the antenna SMA cable through the enclosure grommet
- Use an SMA bulkhead connector for a clean pass-through
- Keep the RTL-SDR dongle inside the enclosure (away from rain)
- Add silica gel desiccant packets inside the enclosure
- Use a drip loop on all cables entering the enclosure

### 13.3 Temperature Range

The Allwinner T527 is rated for -20C to 70C junction temperature.
In an outdoor enclosure:
- Direct sunlight can push internal temps above 60C in summer
- Add ventilation holes (covered with fine mesh) or a small fan
- White or reflective enclosure helps
- Monitor: log thermal_zone0 temperature via cron

### 13.4 Lightning/Surge Protection

If the antenna is mounted high (roof, pole):
```
Antenna ── SMA surge protector ── RTL-SDR ── Orange Pi
                    │
                  Ground wire to earth ground
```
Use an SMA gas discharge tube or TVS diode surge protector (~$15-25).

---

## 14. Multi-Station Architecture

```
                           ┌──────────────┐
┌──────────────┐          │   Desktop     │
│ Orange Pi #1 │──Tailscale──▶│ (Central)    │
│ (Location A) │           │              │
│ sentinel.py  │           │ - ntfy server │
└──────────────┘           │ - tag_server  │
                           │ - dashboard   │
┌──────────────┐           │ - rf_ml.py    │
│ Orange Pi #2 │──Tailscale──▶│ - Neo4j KG   │
│ (Location B) │           │ - GPU (1080)  │
│ sentinel.py  │           │              │
└──────────────┘           └──────────────┘
                                  │
┌──────────────┐                  │
│ Orange Pi #3 │──Tailscale──▶────┘
│ (Mobile/Car) │
│ sentinel.py  │
└──────────────┘
```

Each edge station runs sentinel.py independently and pushes results to the
central server. The desktop handles:
- Heavy ML analysis (rf_ml.py with GPU)
- Knowledge graph (Neo4j)
- Dashboard aggregation
- Paper analysis pipeline

To distinguish stations, set a station ID environment variable:

```bash
# On each Orange Pi, add to .env:
STATION_ID=opi-home
# or: STATION_ID=opi-office
# or: STATION_ID=opi-mobile

# Modify RESULTS_DIR to include station ID:
RESULTS_DIR=/home/tyler/projects/rf-monitor/results/${STATION_ID}
```

---

## 15. Monitoring the Monitor

### 15.1 Health Check Script

```bash
cat > /home/tyler/projects/rf-monitor/health_check.sh << 'SCRIPT'
#!/bin/bash
# ARTEMIS Edge Station Health Check
# Run via cron every 5 minutes, push status to ntfy

NTFY_URL="http://100.96.113.92:8090/artemis-health"
STATION_ID="${STATION_ID:-opi-unknown}"

# Check sentinel is running
SENTINEL_PID=$(pgrep -f "python3 sentinel.py")
if [ -z "$SENTINEL_PID" ]; then
    STATUS="SENTINEL DOWN"
    PRIORITY="high"
else
    STATUS="OK"
    PRIORITY="low"
fi

# Check RTL-SDR is connected
if ! lsusb | grep -qi "0bda:2838\|realtek"; then
    STATUS="${STATUS} | SDR DISCONNECTED"
    PRIORITY="high"
fi

# System stats
TEMP=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null)
TEMP_C=$((TEMP / 1000))
DISK_FREE=$(df -h / | awk 'NR==2{print $4}')
MEM_FREE=$(free -m | awk 'NR==2{print $7}')
UPTIME=$(uptime -p)
LOAD=$(cat /proc/loadavg | awk '{print $1}')

# Latest sentinel cycle age
LATEST_LOG=$(ls -t results/sentinel_*.jsonl 2>/dev/null | head -1)
if [ -n "$LATEST_LOG" ]; then
    LAST_MOD=$(stat -c %Y "$LATEST_LOG")
    NOW=$(date +%s)
    AGE_MIN=$(( (NOW - LAST_MOD) / 60 ))
    if [ $AGE_MIN -gt 10 ]; then
        STATUS="${STATUS} | LOG STALE (${AGE_MIN}min)"
        PRIORITY="high"
    fi
fi

# Only push on errors or every 6 hours for heartbeat
HOUR=$(date +%H)
if [ "$STATUS" != "OK" ] || [ "$HOUR" = "00" ] || [ "$HOUR" = "06" ] || [ "$HOUR" = "12" ] || [ "$HOUR" = "18" ]; then
    curl -s -X POST "$NTFY_URL" \
        -H "Title: ${STATION_ID}: ${STATUS}" \
        -H "Priority: ${PRIORITY}" \
        -H "Tags: ${STATION_ID}" \
        -d "Temp: ${TEMP_C}C | Load: ${LOAD} | Disk: ${DISK_FREE} | RAM: ${MEM_FREE}MB | ${UPTIME}" \
        > /dev/null 2>&1
fi
SCRIPT
chmod +x /home/tyler/projects/rf-monitor/health_check.sh

# Add to crontab
# */5 * * * * STATION_ID=opi-home /home/tyler/projects/rf-monitor/health_check.sh
```

### 15.2 Remote Access via SSH

```bash
# From your desktop, jump into the Orange Pi anytime:
ssh tyler@artemis-opi

# Live sentinel output:
tail -f ~/projects/rf-monitor/results/sentinel_stdout.log

# Current cycle data:
tail -1 ~/projects/rf-monitor/results/sentinel_*.jsonl | python3 -m json.tool

# System health:
htop
cat /sys/class/thermal/thermal_zone0/temp
df -h
```

---

## 16. Quick Start Checklist

```
[ ] 1. Flash Ubuntu/Debian server image to microSD
[ ] 2. Insert microSD, connect Ethernet, plug in RTL-SDR, power on
[ ] 3. SSH in, change password, create user
[ ] 4. apt update && apt upgrade
[ ] 5. Install build deps (build-essential, libusb-1.0-0-dev, etc.)
[ ] 6. Build and install rtl-sdr from source
[ ] 7. Configure udev rules, blacklist DVB drivers, reboot
[ ] 8. Verify: rtl_test -t (as non-root user)
[ ] 9. Clone rf-monitor repo
[ ] 10. Create venv, install requirements-edge.txt
[ ] 11. Test: python3 sentinel.py --duration 300
[ ] 12. Create .env file with server IPs
[ ] 13. Install systemd services (sentinel, dashboard, tags)
[ ] 14. Enable and start services
[ ] 15. Set up cron jobs (autopush, health check, thermal log)
[ ] 16. Install Tailscale for secure remote access
[ ] 17. Verify data appears on central server
[ ] 18. (Optional) Install NVMe SSD for IQ captures
[ ] 19. (Optional) Set up UPS for continuous operation
[ ] 20. (Optional) Deploy in outdoor enclosure
```

---

## 17. Troubleshooting

### RTL-SDR Not Detected

```bash
# Check USB
lsusb
# If not listed, try different USB port or cable

# Check kernel driver conflict
lsmod | grep dvb
# If dvb_usb_rtl28xxu is loaded, blacklist didn't take effect:
rmmod dvb_usb_rtl28xxu
# Then re-check modprobe blacklist config and reboot

# Check udev rules
udevadm info -a /dev/bus/usb/001/002 | grep idVendor
# Verify vendor/product IDs match your rules
```

### Sentinel Crashes or Hangs

```bash
# Check logs
journalctl -u artemis-sentinel --since "1 hour ago"
tail -50 results/sentinel_stderr.log

# Common causes:
# 1. RTL-SDR disconnected → sentinel handles this (retries)
# 2. Out of disk space → sentinel checks this (stops IQ saves)
# 3. Out of memory → add swap, reduce stare-pairs
# 4. Thermal throttle → add heatsink, check temperature
```

### Poor IQ Quality / Sample Drops

```bash
# Reduce sample rate (edit SAMPLE_RATE in sentinel.py)
# 2.4 Msps → 1.8 Msps or 1.0 Msps
# This reduces CPU and USB load at the cost of bandwidth

# Check CPU frequency
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq
# All should show 1800000 (1.8 GHz) if performance governor is set

# Check USB errors
dmesg | grep -i usb | tail -20
```

### NPU Not Working

```bash
# Check if NPU device exists
ls /dev/npu* 2>/dev/null || ls /dev/galcore* 2>/dev/null
# If not present, the kernel may not have NPU support

# Check kernel module
lsmod | grep galcore
# If not loaded: modprobe galcore

# Verify with awnn
awnn_run --version
```

---

## Sources

- [Orange Pi 4A Official Page](http://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/details/Orange-Pi-4A.html)
- [Orange Pi 4A Wiki](http://www.orangepi.org/orangepiwiki/index.php/Orange_Pi_4A)
- [Orange Pi 4A Review — Tom's Hardware](https://www.tomshardware.com/raspberry-pi/orangepi-4a-review)
- [Orange Pi 4A — CNX Software](https://www.cnx-software.com/2024/11/16/orange-pi-4a-low-cost-octa-core-sbc-is-powered-by-allwinner-t527-cortex-a55-ai-soc-with-a-2tops-npu/)
- [Orange Pi 4A — AndroidPimp Review](https://www.androidpimp.com/embedded/orangepi-4a/)
- [Orange Pi 4A — Electronics Lab](https://www.electronics-lab.com/orange-pi-4a-sbc-powered-by-allwinner-t527-with-mali-g57-gpu-and-2-tops-npu/)
- [Armbian T527 Forum Thread](https://forum.armbian.com/topic/49353-opi-4a-allwinner-t527/)
- [Vivante NPU SDK / ACUITY Toolkit — Radxa Docs](https://docs.radxa.com/en/cubie/a7a/app-dev/npu-dev/cubie_acuity_sdk)
- [Allwinner T527 SDK Release — CNX Software](https://www.cnx-software.com/2025/07/07/allwinner-a527-t527-and-a733-datasheets-user-manuals-and-linux-sdk-released/)
- [RTL-SDR Quick Start Guide](https://www.rtl-sdr.com/rtl-sdr-quick-start-guide/)
- [pyrtlsdr Documentation](https://pyrtlsdr.readthedocs.io/en/latest/Overview.html)
- [RTL-SDR on Orange Pi (Primal Cortex blog)](https://primalcortex.wordpress.com/2016/05/13/orange-pi-pc-armbian-and-sdr/)
- [Sixfab IP65 Outdoor Enclosure](https://sixfab.com/product/raspberry-pi-ip65-outdoor-iot-project-enclosure/)
- [Geekworm UPS HAT X1200](https://geekworm.com/products/x1200)
- [Amazon — Orange Pi 4A 4GB](https://www.amazon.com/Orange-Pi-Allwinner-Co-Processor-Frequency/dp/B0DMZCDJ26)
