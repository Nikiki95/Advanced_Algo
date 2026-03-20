# Multi-stage Build für kleines, sicheres Image
FROM python:3.11-slim as builder

# Build-Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    gfortran \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# Python-Dependencies in virtueller Umgebung installieren
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Playwright Chromium installieren
RUN playwright install chromium
RUN playwright install-deps chromium

# Final Stage - Nur Runtime
FROM python:3.11-slim

# Security: Non-root User
RUN useradd -m -u 1000 betuser && \
    mkdir -p /app /app/data /app/models && \
    chown -R betuser:betuser /app

# Nur notwendige System-Libs für Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxcb1 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Virtuelle Umgebung vom Builder kopieren
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Playwright-Browser vom Builder
COPY --from=builder /root/.cache/ms-playwright /home/betuser/.cache/ms-playwright
RUN chown -R betuser:betuser /home/betuser/.cache

# Application Code
WORKDIR /app
COPY --chown=betuser:betuser . /app

# Security: Read-only außer data/ und models/
VOLUME ["/app/data", "/app/models"]

# Non-root User
USER betuser

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default: Training + Einmal-Check
CMD ["python", "main.py", "--no-notify"]