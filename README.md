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

# One-time: interactive login (see section below)
# After that you will have state/storage_state.json.

# Start scheduler
docker compose up -d
docker compose logs -f talenta-bot   # verify supercronic output
```

## First-time login (interactive, required once)

Automated password auto-fill fails for accounts using Google OAuth, 2FA, or
any Mekari flow beyond plain email+password. The reliable approach is to
log in manually once in a visible browser; Playwright saves the session to
`state/storage_state.json`, and every scheduled run afterwards reuses it.

### Option A — inside Docker with WSLg or X11 (WSL, Linux desktop)

```bash
xhost +local:                        # allow container to talk to display
docker run --rm -it \
  -v "$(pwd)/state:/app/state" \
  --env-file .env \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  --entrypoint "" \
  ghcr.io/bimapangestu28/talenta-automation:latest \
  python -m talenta_bot login
```

A Chromium window opens. Complete the login (Google OAuth, 2FA, whatever).
Once the URL reaches `hr.talenta.co`, the command saves session and exits.

### Option B — on the host (no Docker GUI needed)

Install Playwright system deps then run the package natively:

```bash
sudo apt install -y libnspr4 libnss3 libasound2t64        # or libasound2 on older Ubuntu
uv pip install -e ".[dev]"
.venv/bin/playwright install chromium
HEADLESS=false .venv/bin/python -m talenta_bot login
```

Same outcome: browser opens, you log in, session is captured to `state/storage_state.json`.

### Re-login later

Mekari sessions eventually expire (or you can bust them by deleting
`state/storage_state.json`). When that happens, scheduled runs fail with a
`LoginFailed` Telegram message. Just re-run the same interactive login command
above.

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
