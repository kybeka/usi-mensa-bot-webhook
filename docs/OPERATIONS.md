# Maintainer guide

This guide covers local validation, delivery configuration and the safeguards used by USI Mensa Bot.

## Architecture

- `mensa_bot/source.py` fetches and strictly parses the server-rendered 1908 page.
- `mensa_bot/models.py` defines the weekly menu structure.
- `mensa_bot/rendering.py` creates bounded Telegram HTML and Discord embeds.
- `mensa_bot/delivery.py` contains the Telegram and Discord clients.
- `mensa_bot/job.py` coordinates freshness checks, Monday pinning and daily delivery.
- `mensa_bot/announcement.py` contains the guarded one-time migration announcement.
- `channel_job.py` and `announcement_job.py` are the command entry points.

## Local validation

Use an existing Python environment and install the development requirements into it:

```bash
pip install -r requirements-dev.txt
python -m pytest
DELIVERY_MODE=dry-run python channel_job.py
DELIVERY_MODE=dry-run python announcement_job.py
```

`dry-run` is the default delivery mode. It fetches and validates the live 1908 page, then prints the Telegram and Discord payloads without contacting either platform.

## Deployment

Configure at least one destination with GitHub Actions secrets:

- Telegram: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
- Discord: `DISCORD_WEBHOOK_URL`

The official deployment publishes to Telegram. Fork owners can add their own Discord webhook URL to publish the same menu to a Discord channel.

The Telegram bot must be a channel administrator with permission to edit messages so it can pin the Monday overview.

Scheduled runs use `DELIVERY_MODE=live`. Manual workflow runs default to `dry-run`; a live run is accepted only from the default branch.

## Delivery safeguards

- The workflow runs once each weekday at 05:00 UTC. Its local delivery gate accepts delayed scheduled runs from 06:00 through 17:59 Europe/Zurich, covering both summer and winter time.
- Live runs are serialized so two deliveries cannot start concurrently.
- Before sending, the workflow validates the complete payload and checks for a seven-day artifact named `menu-delivery-YYYY-MM-DD`.
- The artifact is acquired before either platform is contacted. A second live run for the same Zurich date stops before delivery.
- Successful or active scheduled runs made before the artifact lock existed are also recognized.
- Dry runs never create a delivery lock.

If a live run fails after acquiring its artifact, delete that artifact only after confirming that no message reached either platform.

## Monday behavior

On Monday, the bot sends the compact weekly overview before the detailed daily menu. It pins the overview on Telegram. Incoming Discord webhooks cannot manage pins, so the overview is posted there without pinning.

The overview describes the week starting that morning. If 1908 has not published the current week, the job fails without sending stale content.

## One-time migration announcement

The migration announcement workflow is manually triggered and protected against successful repeat runs. It also requires this confirmation:

```text
ANNOUNCEMENT_CONFIRM=publish-1908-migration
```

Each fork has an independent workflow history and can therefore send its own announcement once.

## Failure behavior

No subscriber-facing fallback is sent for network, freshness or parsing failures. The GitHub Actions run fails and records the reason instead.

Closed weekdays are accepted only when the source contains an explicit closure notice. An unexplained empty panel is treated as a structural failure.
