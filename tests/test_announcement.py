import pytest

from mensa_bot.announcement import (
    CONFIRMATION_VALUE,
    discord_announcement,
    run_announcement,
    telegram_announcement,
)
from mensa_bot.config import DeliveryMode, Settings


class FakeTelegram:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.pin_permission_checked = False

    def assert_can_pin(self) -> None:
        self.pin_permission_checked = True

    def send_html(self, text: str) -> int:
        self.messages.append(text)
        return 1


class FakeDiscord:
    def __init__(self) -> None:
        self.payloads: list[dict] = []

    def send(self, payload: dict) -> None:
        self.payloads.append(payload)


def test_announcement_mentions_1908_and_reporting_channel() -> None:
    telegram = telegram_announcement()
    discord = discord_announcement()

    assert "1908" in telegram
    assert "🇮🇹 <b>Italiano</b>" in telegram
    assert "🇬🇧 <b>English</b>" in telegram
    assert "The campus catering provider changed" in telegram
    assert "Report a problem" in telegram
    assert "1908" in discord["embeds"][0]["description"]
    assert "🇮🇹 **Italiano**" in discord["embeds"][0]["description"]
    assert "🇬🇧 **English**" in discord["embeds"][0]["description"]
    assert "The campus catering provider changed" in discord["embeds"][0]["description"]
    assert discord["allowed_mentions"] == {"parse": []}


def test_live_announcement_requires_exact_confirmation() -> None:
    settings = Settings(
        delivery_mode=DeliveryMode.LIVE,
        telegram_bot_token="token",
        telegram_chat_id="chat",
        discord_webhook_url="https://discord.example/webhook",
    )
    with pytest.raises(RuntimeError, match="ANNOUNCEMENT_CONFIRM"):
        run_announcement(
            settings,
            telegram=FakeTelegram(),
            discord=FakeDiscord(),
            confirmation="wrong",
        )


def test_confirmed_announcement_sends_once_to_each_platform() -> None:
    settings = Settings(
        delivery_mode=DeliveryMode.LIVE,
        telegram_bot_token="token",
        telegram_chat_id="chat",
        discord_webhook_url="https://discord.example/webhook",
    )
    telegram = FakeTelegram()
    discord = FakeDiscord()

    run_announcement(
        settings,
        telegram=telegram,
        discord=discord,
        confirmation=CONFIRMATION_VALUE,
    )

    assert len(telegram.messages) == 1
    assert len(discord.payloads) == 1
    assert telegram.pin_permission_checked is True


def test_confirmed_announcement_supports_telegram_only() -> None:
    settings = Settings(
        delivery_mode=DeliveryMode.LIVE,
        telegram_bot_token="token",
        telegram_chat_id="chat",
    )
    telegram = FakeTelegram()

    run_announcement(
        settings,
        telegram=telegram,
        confirmation=CONFIRMATION_VALUE,
    )

    assert len(telegram.messages) == 1
    assert telegram.pin_permission_checked is True


def test_confirmed_announcement_supports_discord_only() -> None:
    settings = Settings(
        delivery_mode=DeliveryMode.LIVE,
        discord_webhook_url="https://discord.example/webhook",
    )
    discord = FakeDiscord()

    run_announcement(
        settings,
        discord=discord,
        confirmation=CONFIRMATION_VALUE,
    )

    assert len(discord.payloads) == 1


def test_confirmed_announcement_requires_a_destination() -> None:
    settings = Settings(delivery_mode=DeliveryMode.LIVE)

    with pytest.raises(RuntimeError, match="configured delivery destination"):
        run_announcement(settings, confirmation=CONFIRMATION_VALUE)
