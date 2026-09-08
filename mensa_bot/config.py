import os
from dataclasses import dataclass
from enum import StrEnum

from .source import DEFAULT_MENU_URL


class DeliveryMode(StrEnum):
    DRY_RUN = "dry-run"
    LIVE = "live"


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    menu_url: str = DEFAULT_MENU_URL
    timezone: str = "Europe/Zurich"
    delivery_mode: DeliveryMode = DeliveryMode.DRY_RUN
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""
    pin_monday_overview: bool = True
    send_hour_local: int = 7
    send_window_hours: int = 8
    fetch_retries: int = 3
    fetch_retry_backoff_seconds: float = 3
    request_timeout_seconds: float = 30
    github_event_name: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        raw_mode = os.getenv("DELIVERY_MODE", DeliveryMode.DRY_RUN.value).strip().casefold()
        try:
            mode = DeliveryMode(raw_mode)
        except ValueError as exc:
            raise RuntimeError("DELIVERY_MODE must be 'dry-run' or 'live'.") from exc

        settings = cls(
            menu_url=os.getenv("MENU_URL", DEFAULT_MENU_URL).strip(),
            timezone=os.getenv("TIMEZONE", "Europe/Zurich").strip(),
            delivery_mode=mode,
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", "").strip(),
            pin_monday_overview=_env_bool("PIN_MONDAY_OVERVIEW", True),
            send_hour_local=int(os.getenv("SEND_HOUR_LOCAL", "7")),
            send_window_hours=int(os.getenv("SEND_WINDOW_HOURS", "8")),
            fetch_retries=int(os.getenv("FETCH_RETRIES", "3")),
            fetch_retry_backoff_seconds=float(os.getenv("FETCH_RETRY_BACKOFF_SECONDS", "3")),
            request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30")),
            github_event_name=os.getenv("GITHUB_EVENT_NAME", "").strip(),
        )
        settings.validate()
        return settings

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def discord_enabled(self) -> bool:
        return bool(self.discord_webhook_url)

    def validate(self) -> None:
        if not self.menu_url.startswith("https://"):
            raise RuntimeError("MENU_URL must use HTTPS.")
        if self.fetch_retries < 1:
            raise RuntimeError("FETCH_RETRIES must be at least 1.")
        if self.delivery_mode is DeliveryMode.LIVE and not (
            self.telegram_enabled or self.discord_enabled
        ):
            raise RuntimeError(
                "Live delivery requires Telegram credentials and/or a Discord webhook URL."
            )
