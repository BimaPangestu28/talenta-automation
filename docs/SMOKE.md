# Post-deploy smoke checklist

Run these after every `docker compose build && docker compose up -d`.

## First-time (selector verification)

Because `src/talenta_bot/selectors.py` was seeded with best-guess values,
run this verification the first time. Re-run whenever Talenta UI changes.

- [ ] `docker compose run --rm talenta-bot python -m talenta_bot login` → exit 0, `state/storage_state.json` created, no `LoginFailed` Telegram.
- [ ] `docker compose run --rm talenta-bot python -m talenta_bot clock-in --dry-run` → logs "would click Clock In button" with no `SelectorNotFound`. If it fails, inspect selectors.py against the live Mekari/Talenta DOM and fix.

## Happy path

- [ ] On a weekday, in the clock-in window: `clock-in --now --skip-window` → ✅ Telegram message AND Talenta web shows today's entry.
- [ ] Later in the day: `clock-out --now --skip-window` → ✅ Telegram message AND Talenta shows clock-out time.

## Error handling

- [ ] Remove `state/storage_state.json`, rerun `clock-in --now --skip-window --dry-run` → auto-relogin, new state file appears.
- [ ] Temporarily change `.env` password to something wrong, run `clock-in --now --skip-window` → 🚨 Telegram message with `LoginFailed`. Restore password after.

## Idempotency

- [ ] Right after a successful clock-in, run `clock-in --now --skip-window` again → ℹ️ Telegram "skipped, tercatat HH:MM".

## Scheduler

- [ ] `docker compose logs --tail 50 talenta-bot` → supercronic "cron job started" / "serving cronfile" lines visible.
- [ ] Cron entries on the correct TZ: inspect `docker compose exec talenta-bot date` — should return Asia/Jakarta.
