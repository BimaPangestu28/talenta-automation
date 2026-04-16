FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Jakarta

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

CMD ["supercronic", "/app/crontab"]
