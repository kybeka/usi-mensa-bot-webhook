import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable
from zoneinfo import ZoneInfo

from .config import DeliveryMode, Settings
from .delivery import DeliveryError, DiscordPublisher, TelegramPublisher
from .models import WeeklyMenu
from .rendering import (
    render_discord_day,
    render_discord_week,
    render_telegram_day,
    render_telegram_week,
)
from .source import MenuError, MenuFetchError, fetch_weekly_menu, require_current_week


@dataclass(frozen=True)
class JobOutcome:
    published_week: int | None
    weekly_sent: bool
    weekly_pinned: bool
    daily_sent: bool
    skipped_reason: str | None = None


def _fetch_with_retry(
    settings: Settings,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> WeeklyMenu:
    last_error: MenuFetchError | None = None
    for attempt in range(1, settings.fetch_retries + 1):
        try:
            return fetch_weekly_menu(
                settings.menu_url,
                timeout_seconds=settings.request_timeout_seconds,
            )
        except MenuFetchError as exc:
            last_error = exc
            if attempt == settings.fetch_retries:
                break
            delay = settings.fetch_retry_backoff_seconds * attempt
            print(
                f"WARN fetch attempt={attempt}/{settings.fetch_retries} "
                f"retry_in_seconds={delay:g} error={exc}"
            )
            sleep(delay)
    raise MenuFetchError(
        f"Menu fetch failed after {settings.fetch_retries} attempts: {last_error}"
    )


def _print_dry_run(label: str, telegram_text: str, discord_payload: dict) -> None:
    print(f"DRY_RUN platform=telegram message={label}\n{telegram_text}")
    print(
        f"DRY_RUN platform=discord message={label}\n"
        + json.dumps(discord_payload, ensure_ascii=False, indent=2)
    )


def run_job(
    settings: Settings,
    *,
    now: datetime | None = None,
    menu: WeeklyMenu | None = None,
    telegram: TelegramPublisher | None = None,
    discord: DiscordPublisher | None = None,
) -> JobOutcome:
    now_local = now or datetime.now(ZoneInfo(settings.timezone))
    if now_local.tzinfo is None:
        now_local = now_local.replace(tzinfo=ZoneInfo(settings.timezone))
    else:
        now_local = now_local.astimezone(ZoneInfo(settings.timezone))

    if now_local.weekday() > 4:
        return JobOutcome(None, False, False, False, "weekend")

    if settings.github_event_name == "schedule":
        window_end = settings.send_hour_local + settings.send_window_hours
        if not settings.send_hour_local <= now_local.hour < window_end:
            return JobOutcome(None, False, False, False, "outside_send_window")

    weekly_menu = menu or _fetch_with_retry(settings)
    target_date = now_local.date()
    require_current_week(weekly_menu, target_date)
    today_menu = weekly_menu.menu_for(target_date)
    if today_menu is None:
        raise MenuError(f"No parsed menu exists for {target_date.isoformat()}.")

    weekly_sent = False
    weekly_pinned = False
    pin_error: DeliveryError | None = None

    if target_date.weekday() == 0:
        telegram_week = render_telegram_week(weekly_menu)
        discord_week = render_discord_week(weekly_menu)
        if settings.delivery_mode is DeliveryMode.DRY_RUN:
            _print_dry_run("weekly", telegram_week, discord_week)
        else:
            if telegram is not None:
                weekly_message_id = telegram.send_html(telegram_week)
                weekly_sent = True
                if settings.pin_monday_overview:
                    try:
                        telegram.pin(weekly_message_id)
                        weekly_pinned = True
                    except DeliveryError as exc:
                        pin_error = exc
                        print(f"ERROR weekly_pin_failed message_id={weekly_message_id} error={exc}")
            if discord is not None:
                discord.send(discord_week)
                weekly_sent = True
        print(
            f"OUTCOME type=weekly week={weekly_menu.week_number} "
            f"delivery_mode={settings.delivery_mode.value} pinned={weekly_pinned}"
        )

    if today_menu.items:
        telegram_day = render_telegram_day(weekly_menu, today_menu)
        discord_day = render_discord_day(weekly_menu, today_menu)
        if settings.delivery_mode is DeliveryMode.DRY_RUN:
            _print_dry_run("daily", telegram_day, discord_day)
        else:
            if telegram is not None:
                telegram.send_html(telegram_day)
            if discord is not None:
                discord.send(discord_day)
        daily_sent = settings.delivery_mode is DeliveryMode.LIVE
        print(
            f"OUTCOME type=daily date={target_date.isoformat()} "
            f"items={len(today_menu.items)} delivery_mode={settings.delivery_mode.value}"
        )
    else:
        daily_sent = False
        print(
            f"OUTCOME type=closed date={target_date.isoformat()} "
            f"reason={today_menu.closure_note!r}"
        )

    if pin_error is not None:
        raise DeliveryError(
            "The weekly menu was delivered, but Telegram could not pin it. "
            "Ensure the bot is a channel administrator with can_edit_messages permission."
        ) from pin_error

    return JobOutcome(
        published_week=weekly_menu.week_number,
        weekly_sent=weekly_sent,
        weekly_pinned=weekly_pinned,
        daily_sent=daily_sent,
    )


def main() -> int:
    try:
        settings = Settings.from_env()
        telegram = (
            TelegramPublisher(settings.telegram_bot_token, settings.telegram_chat_id)
            if settings.delivery_mode is DeliveryMode.LIVE and settings.telegram_enabled
            else None
        )
        discord = (
            DiscordPublisher(settings.discord_webhook_url)
            if settings.delivery_mode is DeliveryMode.LIVE and settings.discord_enabled
            else None
        )
        outcome = run_job(settings, telegram=telegram, discord=discord)
        print(f"JOB_RESULT {outcome}")
        return 0
    except (MenuError, DeliveryError, RuntimeError) as exc:
        print(f"JOB_FAILED error={exc}")
        return 1
