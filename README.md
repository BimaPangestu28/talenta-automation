# Talenta Auto Clock-In/Out

Runs unattended on a VPS via Docker. Clocks in and out on Talenta (Mekari HR)
on weekdays within configurable randomised windows, with Telegram notifications.

## Requirements

- Linux VPS with `docker` and `docker compose`
- Outbound HTTPS to `*.mekari.com`, `*.talenta.co`, `api.telegram.org`
- Mekari account without 2FA
- Telegram bot token + chat id

## First-time setup (VPS, using prebuilt image from GHCR)

```bash
git clone git@github.com:BimaPangestu28/talenta-automation.git ~/talenta-automation
cd ~/talenta-automation
cp .env.example .env && $EDITOR .env
mkdir -p state && chmod 700 state
chmod 600 .env

# Auth to GHCR (image is private by default). Create a PAT at
# https://github.com/settings/tokens with `read:packages` scope.
echo "$GHCR_TOKEN" | docker login ghcr.io -u BimaPangestu28 --password-stdin

# Pull prebuilt image (published by CI on every master push)
docker compose pull

# One-time: warm up session
docker compose run --rm talenta-bot python -m talenta_bot login

# Start scheduler
docker compose up -d
docker compose logs -f talenta-bot   # verify supercronic output
```

## Updating

```bash
git pull
docker compose pull          # grab fresh image from GHCR
docker compose up -d         # recreate container on new image
```

If you prefer to build locally instead of pulling, use `docker compose build`.

## Selectors

`src/talenta_bot/selectors.py` currently holds **best-guess** CSS/role selectors.
During first smoke test, verify each one matches the live Talenta + Mekari UI
(see `docs/SMOKE.md`). If a selector is wrong, edit the file and rebuild.

## Operations

```bash
# Test a run manually (bypass schedule & window)
docker compose run --rm talenta-bot python -m talenta_bot clock-in --now --skip-window

# Dry-run (navigate, do not click)
docker compose run --rm talenta-bot python -m talenta_bot clock-in --dry-run

# Tail logs
docker compose logs --tail 100 talenta-bot

# Update after pulling changes
git pull && docker compose build && docker compose up -d
```

## Running tests

Unit tests run in any Python ≥3.10 environment:

```bash
uv venv --python 3.12 .venv    # or python -m venv
uv pip install -e ".[dev]"
.venv/bin/pytest tests/unit/
```

Integration test needs Chromium + its system libraries. Easiest to run inside
the built image:

```bash
docker compose run --rm -e RUN_INTEGRATION=1 talenta-bot pytest tests/integration/
```

## Troubleshooting

- **LoginFailed**: verify `MEKARI_EMAIL` / `MEKARI_PASSWORD`, then rerun `login`.
- **Session expired**: delete `state/storage_state.json` and run `login` again.
- **Selectors not found**: Talenta UI likely changed — update `src/talenta_bot/selectors.py`, rebuild.
- **No Telegram messages**: test with `curl -d chat_id=<ID> -d text=hi "https://api.telegram.org/bot<TOKEN>/sendMessage"`.

## Design & plan

- Spec: `docs/superpowers/specs/2026-04-16-talenta-automation-design.md`
- Plan: `docs/superpowers/plans/2026-04-16-talenta-automation.md`
- Post-deploy smoke checklist: `docs/SMOKE.md`
