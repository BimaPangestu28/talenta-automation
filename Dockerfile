FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Jakarta

# System tzdata + /etc/localtime — supercronic is a Go binary and needs
# /usr/share/zoneinfo/$TZ to honor the TZ env var; the Python tzdata wheel
# does not help it. Without this, supercronic silently falls back to UTC
# and cron expressions fire on the wrong wall-clock time.
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata \
 && ln -sf /usr/share/zoneinfo/Asia/Jakarta /etc/localtime \
 && echo "Asia/Jakarta" > /etc/timezone \
 && rm -rf /var/lib/apt/lists/*

# supercronic — cron alternative for containers (logs to stdout, no forking)
ARG SUPERCRONIC_VERSION=v0.2.33
RUN curl -fsSLo /usr/local/bin/supercronic \
      "https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-amd64" \
 && chmod +x /usr/local/bin/supercronic

WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e .

COPY crontab ./crontab

# Non-root user — Playwright base image ships with pwuser (uid 1000)
RUN mkdir -p /app/state && chown -R pwuser:pwuser /app
USER pwuser

# -no-reap: let the container init (tini via `init: true` in compose)
# handle zombie reaping instead of supercronic. Supercronic's own reaper
# fork+execs /proc/self/exe every minute which fails in some runtimes.
CMD ["supercronic", "-no-reap", "/app/crontab"]
