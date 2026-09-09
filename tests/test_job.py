from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from mensa_bot.config import DeliveryMode, Settings
from mensa_bot.job import run_job
from mensa_bot.source import PublishedWeekMismatch


class FakeTelegram:
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []

    def send_html(self, text: str) -> int:
        message_id = len([event for event in self.events if event[0] == "send"]) + 1
        self.events.append(("send", text))
        return message_id

    def pin(self, message_id: int) -> None:
        self.events.append(("pin", message_id))


class FakeDiscord:
    def __init__(self) -> None:
        self.payloads: list[dict] = []

    def send(self, payload: dict) -> None:
        self.payloads.append(payload)


def live_settings() -> Settings:
    return Settings(
        delivery_mode=DeliveryMode.LIVE,
        telegram_bot_token="token",
        telegram_chat_id="chat",
        discord_webhook_url="https://discord.example/webhook",
    )


def test_monday_sends_weekly_then_daily_and_pins_weekly(weekly_menu) -> None:
    telegram = FakeTelegram()
    discord = FakeDiscord()

    outcome = run_job(
        live_settings(),
        now=datetime(2026, 9, 7, 10, tzinfo=ZoneInfo("Europe/Zurich")),
        menu=weekly_menu,
        telegram=telegram,
        discord=discord,
    )

    assert [event[0] for event in telegram.events] == ["send", "pin", "send"]
    assert telegram.events[1] == ("pin", 1)
    assert len(discord.payloads) == 2
    assert outcome.weekly_sent is True
    assert outcome.weekly_pinned is True
    assert outcome.daily_sent is True


def test_tuesday_sends_only_daily(weekly_menu) -> None:
    telegram = FakeTelegram()
    discord = FakeDiscord()

    outcome = run_job(
        live_settings(),
        now=datetime(2026, 9, 8, 10, tzinfo=ZoneInfo("Europe/Zurich")),
        menu=weekly_menu,
        telegram=telegram,
        discord=discord,
    )

    assert [event[0] for event in telegram.events] == ["send"]
    assert len(discord.payloads) == 1
    assert outcome.weekly_sent is False
    assert outcome.daily_sent is True


def test_stale_week_fails_before_delivery(weekly_menu) -> None:
    telegram = FakeTelegram()
    discord = FakeDiscord()

    with pytest.raises(PublishedWeekMismatch):
        run_job(
            live_settings(),
            now=datetime(2026, 9, 14, 10, tzinfo=ZoneInfo("Europe/Zurich")),
            menu=weekly_menu,
            telegram=telegram,
            discord=discord,
        )

    assert telegram.events == []
    assert discord.payloads == []


def test_dry_run_needs_no_delivery_credentials(weekly_menu, capsys) -> None:
    outcome = run_job(
        Settings(),
        now=datetime(2026, 9, 7, 10, tzinfo=ZoneInfo("Europe/Zurich")),
        menu=weekly_menu,
    )

    output = capsys.readouterr().out
    assert "DRY_RUN platform=telegram message=weekly" in output
    assert "DRY_RUN platform=discord message=daily" in output
    assert outcome.weekly_sent is False
    assert outcome.daily_sent is False
