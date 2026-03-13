FROM python:3.12-slim AS base

# System deps: rtl-sdr + build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    rtl-sdr librtlsdr-dev libusb-1.0-0-dev \
    tesseract-ocr \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Blacklist kernel driver so rtl_sdr userspace works
RUN echo "blacklist dvb_usb_rtl28xxu" > /etc/modprobe.d/blacklist-rtl.conf

WORKDIR /app

# Install Python deps — torch first (large cached layer)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install remaining deps (cached layer)
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

# Copy application code
COPY *.py ./
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create data directories
RUN mkdir -p /data/results/evidence /data/captures /data/papers /data/knowledge_graph

# Non-root user for runtime (needs USB group for SDR access)
RUN groupadd -r rfmon && useradd -r -g rfmon -G plugdev -d /app rfmon \
    && chown -R rfmon:rfmon /app /data

# Healthcheck: verify sentinel checkpoint is fresh (< 10 min old)
HEALTHCHECK --interval=5m --timeout=10s --retries=3 --start-period=3m \
    CMD python -c "import os,time; s=os.stat('/data/results/sentinel_checkpoint.json'); assert time.time()-s.st_mtime<600" 2>/dev/null || true

USER rfmon

ENTRYPOINT ["/entrypoint.sh"]
CMD ["sentinel.py", "--duration", "2592000", "--iq-budget-mb", "10000"]
