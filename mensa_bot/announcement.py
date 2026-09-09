import json
import os

from .config import DeliveryMode, Settings
from .delivery import DeliveryError, DiscordPublisher, TelegramPublisher
from .rendering import DISCORD_COLOR, validate_telegram

CONFIRMATION_VALUE = "publish-1908-migration"
REPORT_URL = "https://github.com/kybeka/usi-mensa-bot-webhook/issues"


def telegram_announcement() -> str:
    return validate_telegram(
        "🍽️ <b>USI Mensa Bot: aggiornamento / service update</b>\n\n"
        "🇮🇹 <b>Italiano</b>\n"
        "Durante l’estate è cambiato il gestore della ristorazione dei campus. "
        "Il bot è stato aggiornato e ora legge i menù pubblicati da <b>1908</b> "
        "per Campus Est USI–SUPSI, Campus Ovest USI e Campus SUPSI Mendrisio.\n\n"
        "I messaggi giornalieri e il riepilogo settimanale del lunedì seguiranno "
        "il nuovo sito ufficiale.\n\n"
        "🇬🇧 <b>English</b>\n"
        "The campus catering provider changed over the summer. The bot has been "
        "updated and now reads the menus published by <b>1908</b> for USI–SUPSI "
        "East Campus, USI West Campus and SUPSI Mendrisio Campus.\n\n"
        "Daily messages and the Monday weekly overview will now follow the new "
        "official website.\n\n"
        f'<a href="{REPORT_URL}">Segnala un problema / Report a problem</a>\n'
        '<a href="https://menu.1908.ch/usi-supsi">Menù ufficiale / Official menu</a>'
    )


def discord_announcement() -> dict:
    return {
        "allowed_mentions": {"parse": []},
        "embeds": [
            {
                "title": "🍽️ USI Mensa Bot: aggiornamento / service update",
                "url": "https://menu.1908.ch/usi-supsi",
                "description": (
                    "🇮🇹 **Italiano**\n"
                    "Durante l’estate è cambiato il gestore della ristorazione dei campus. "
                    "Il bot è stato aggiornato e ora legge i menù pubblicati da **1908** "
                    "per Campus Est USI–SUPSI, Campus Ovest USI e Campus SUPSI Mendrisio.\n\n"
                    "I messaggi giornalieri e il riepilogo settimanale del lunedì seguiranno "
                    "il nuovo sito ufficiale.\n\n"
                    "🇬🇧 **English**\n"
                    "The campus catering provider changed over the summer. The bot has been "
                    "updated and now reads the menus published by **1908** for USI–SUPSI "
                    "East Campus, USI West Campus and SUPSI Mendrisio Campus.\n\n"
                    "Daily messages and the Monday weekly overview will now follow the new "
                    "official website.\n\n"
                    f"[Segnala un problema / Report a problem]({REPORT_URL})"
                ),
                "color": DISCORD_COLOR,
            }
        ],
    }


def run_announcement(
    settings: Settings,
    *,
    telegram: TelegramPublisher | None = None,
    discord: DiscordPublisher | None = None,
    confirmation: str = "",
) -> None:
    telegram_text = telegram_announcement()
    discord_payload = discord_announcement()
    if settings.delivery_mode is DeliveryMode.DRY_RUN:
        print(f"DRY_RUN platform=telegram message=migration\n{telegram_text}")
        print(
            "DRY_RUN platform=discord message=migration\n"
            + json.dumps(discord_payload, ensure_ascii=False, indent=2)
        )
        return

    if confirmation != CONFIRMATION_VALUE:
        raise RuntimeError(
            f"Set ANNOUNCEMENT_CONFIRM={CONFIRMATION_VALUE!r} for the one-time live announcement."
        )
    if telegram is None and discord is None:
        raise RuntimeError("The migration announcement requires a configured delivery destination.")

    platforms: list[str] = []
    if telegram is not None:
        telegram.assert_can_pin()
        telegram.send_html(telegram_text)
        platforms.append("telegram")
    if discord is not None:
        discord.send(discord_payload)
        platforms.append("discord")
    print(f"OUTCOME type=migration_announcement platforms={','.join(platforms)}")


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
        run_announcement(
            settings,
            telegram=telegram,
            discord=discord,
            confirmation=os.getenv("ANNOUNCEMENT_CONFIRM", ""),
        )
        return 0
    except (DeliveryError, RuntimeError) as exc:
        print(f"ANNOUNCEMENT_FAILED error={exc}")
        return 1
