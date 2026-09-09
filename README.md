<p align="center">
  <img src="img/tg_bot_pfp.png" alt="USI Mensa Bot avatar" width="200">
</p>

# USI Mensa Bot

[![Send 1908 menu](https://github.com/kybeka/usi-mensa-bot-webhook/actions/workflows/send-channel.yml/badge.svg)](https://github.com/kybeka/usi-mensa-bot-webhook/actions/workflows/send-channel.yml)
![Python](https://img.shields.io/badge/python-3.12-blue)
![1908](https://img.shields.io/badge/menu-1908-E76F51)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
[![Telegram](https://img.shields.io/badge/Telegram-@usi__mensa-26A5E4?logo=telegram&logoColor=white)](https://t.me/usi_mensa)
![Discord](https://img.shields.io/badge/Discord-webhook-5865F2?logo=discord&logoColor=white)

Publishes the current [1908 USI–SUPSI menu](https://menu.1908.ch/usi-supsi) to Telegram and Discord on weekday mornings.

The source page covers Campus Est USI SUPSI Viganello, Campus Ovest USI Lugano and Campus SUPSI Mendrisio. The bot is unofficial and is not affiliated with USI, SUPSI or 1908.

## Behavior

- Fetches the complete weekly page once per run using a normal HTTP request.
- Parses the Italian Monday–Friday menu from the server-rendered HTML.
- Rejects stale weeks, malformed date ranges and unexpected page structures.
- Sends the current day's full menu on weekdays.
- Sends a weekly overview before Monday's daily menu.
- Pins the Monday overview in Telegram.
- Sends the overview to Discord without pinning; incoming Discord webhooks cannot manage channel pins.
- Fails the workflow instead of posting a confusing fallback message when parsing breaks.
- Defaults to dry-run mode, so local and manual validation cannot send accidentally.

The Monday overview describes the week that starts that morning. If 1908 has not published that week yet, the job fails without sending stale content.

## Architecture

- `mensa_bot/source.py` fetches and strictly parses the 1908 page.
- `mensa_bot/models.py` defines the 1908-native weekly menu structure.
- `mensa_bot/rendering.py` creates bounded Telegram HTML and Discord embeds.
- `mensa_bot/delivery.py` contains the Telegram and Discord clients.
- `mensa_bot/job.py` coordinates freshness checks, Monday pinning and daily delivery.
- `mensa_bot/announcement.py` contains the guarded one-time migration announcement.
- `channel_job.py` and `announcement_job.py` are small command entry points.

## Safety modes

`DELIVERY_MODE` accepts two values:

- `dry-run` is the default. It fetches, validates and prints both platform payloads without using credentials.
- `live` enables configured Telegram and Discord publishers.

Manual runs of the delivery workflow default to `dry-run`. Scheduled runs use `live` after the workflow becomes active on the default branch.

The migration announcement uses whichever delivery destinations are configured and requires this
additional confirmation:

```text
ANNOUNCEMENT_CONFIRM=publish-1908-migration
```

It is designed to be triggered exactly once during the cutover.

## Local validation

Use an existing Python environment and install the development requirements into that environment:

```bash
pip install -r requirements-dev.txt
python -m pytest
DELIVERY_MODE=dry-run python channel_job.py
DELIVERY_MODE=dry-run python announcement_job.py
```

Dry-run menu validation still reads the live 1908 page but never contacts Telegram or Discord.

## Deployment

Configure at least one live delivery destination with these Actions secrets:

- Telegram: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
- Discord: `DISCORD_WEBHOOK_URL`

The official deployment publishes to Telegram. Fork owners can add their own Discord webhook URL
to publish the same menu and migration announcement to a Discord channel.

The Telegram bot must be a channel administrator with permission to edit messages so it can pin the Monday overview.

The intended cutover is:

1. Keep v2 on its isolated branch while tests and dry runs are reviewed.
2. Run a live scrape with delivery disabled.
3. Merge v2 only after the generated Telegram and Discord messages are approved.
4. Trigger the one-time migration announcement.
5. Let the replacement scheduled workflow take over; never run the v1 and v2 schedules together.

## Failure policy

No subscriber-facing fallback message is sent for network, freshness or parsing failures. The GitHub Actions run turns red and records the reason instead.

Closed weekdays are accepted only when the source panel contains an explicit closure notice. An unexplained empty panel is treated as a structural failure.

## License

MIT License. See [LICENSE](LICENSE).
