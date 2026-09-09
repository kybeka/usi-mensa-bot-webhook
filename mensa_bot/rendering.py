from datetime import date
from decimal import Decimal
from html import escape
from typing import Any

from .models import DailyMenu, MenuItem, WeeklyMenu

TELEGRAM_TEXT_LIMIT = 4096
DISCORD_FIELD_NAME_LIMIT = 256
DISCORD_FIELD_VALUE_LIMIT = 1024
DISCORD_EMBED_TOTAL_LIMIT = 6000
DISCORD_COLOR = 0xE76F51
MONTHS_IT = (
    "",
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
)


class MessageLimitError(RuntimeError):
    pass


def _date_it(value: date, *, year: bool = False) -> str:
    suffix = f" {value.year}" if year else ""
    return f"{value.day} {MONTHS_IT[value.month]}{suffix}"


def _week_range(menu: WeeklyMenu) -> str:
    if menu.start_date.month == menu.end_date.month:
        date_range = f"{menu.start_date.day}–{_date_it(menu.end_date, year=True)}"
    else:
        date_range = f"{_date_it(menu.start_date)}–{_date_it(menu.end_date, year=True)}"
    return f"{date_range} · Settimana {menu.week_number}"


def _money(value: Decimal | None) -> str | None:
    return f"CHF {value:.2f}" if value is not None else None


def _emoji(category: str) -> str:
    normalized = category.casefold()
    choices = (
        ("vegano", "🥬"),
        ("vegetar", "🌱"),
        ("primo", "🍝"),
        ("secondo", "🍽️"),
        ("contorni", "🥕"),
        ("insalata", "🥗"),
        ("dessert", "🍰"),
    )
    return next((emoji for key, emoji in choices if key in normalized), "🍴")


def _telegram_item(item: MenuItem, *, include_prices: bool) -> str:
    lines = [f"{_emoji(item.category)} <b>{escape(item.category)}</b>", escape(item.name)]
    if item.note:
        lines.append(f"<i>{escape(item.note)}</i>")
    if include_prices:
        prices = (
            ("Studenti", _money(item.prices.students)),
            ("Collaboratori", _money(item.prices.staff)),
            ("Esterni", _money(item.prices.external)),
        )
        rendered = [f"{label}: {value}" for label, value in prices if value]
        if rendered:
            lines.append("💸 " + " · ".join(rendered))
    return "\n".join(lines)


def _telegram_header(title: str, menu: WeeklyMenu) -> str:
    return (
        f"{title}\n"
        f"<b>{escape(_week_range(menu))}</b>\n"
        f"<i>Campus Est · Campus Ovest · SUPSI Mendrisio</i>\n"
        f'<a href="{escape(menu.source_url, quote=True)}">Menù ufficiale 1908</a>'
    )


def validate_telegram(text: str) -> str:
    if len(text) > TELEGRAM_TEXT_LIMIT:
        raise MessageLimitError(
            f"Telegram message is {len(text)} characters; limit is {TELEGRAM_TEXT_LIMIT}."
        )
    return text


def render_telegram_week(menu: WeeklyMenu) -> str:
    sections = [_telegram_header("🗓️ <b>Menù settimanale USI–SUPSI</b>", menu)]
    for day in menu.days:
        if day.items:
            items = "\n".join(
                f"{_emoji(item.category)} {escape(item.category)}: {escape(item.name)}"
                for item in day.items
            )
        else:
            items = escape(day.closure_note or "Chiuso")
        sections.append(f"<b>{escape(day.label)} {_date_it(day.date)}</b>\n{items}")
    return validate_telegram("\n\n".join(sections))


def render_telegram_day(menu: WeeklyMenu, day: DailyMenu) -> str:
    sections = [
        _telegram_header(
            f"🍽️ <b>Menù di {escape(day.label)} {_date_it(day.date)}</b>",
            menu,
        )
    ]
    if day.items:
        sections.extend(_telegram_item(item, include_prices=True) for item in day.items)
    else:
        sections.append(escape(day.closure_note or "Chiuso"))
    return validate_telegram("\n\n".join(sections))


def _discord_item_line(item: MenuItem) -> str:
    return f"{_emoji(item.category)} **{item.category}:** {item.name}"


def _discord_day_field(day: DailyMenu) -> dict[str, Any]:
    value = "\n".join(_discord_item_line(item) for item in day.items)
    if not value:
        value = day.closure_note or "Chiuso"
    return {"name": f"{day.label} {_date_it(day.date)}", "value": value, "inline": False}


def _validate_discord(payload: dict[str, Any]) -> dict[str, Any]:
    for embed in payload.get("embeds", []):
        total = len(embed.get("title", "")) + len(embed.get("description", ""))
        for field in embed.get("fields", []):
            if len(field["name"]) > DISCORD_FIELD_NAME_LIMIT:
                raise MessageLimitError("A Discord field name exceeds 256 characters.")
            if len(field["value"]) > DISCORD_FIELD_VALUE_LIMIT:
                raise MessageLimitError("A Discord field value exceeds 1024 characters.")
            total += len(field["name"]) + len(field["value"])
        if total > DISCORD_EMBED_TOTAL_LIMIT:
            raise MessageLimitError("A Discord embed exceeds 6000 characters.")
    return payload


def render_discord_week(menu: WeeklyMenu) -> dict[str, Any]:
    return _validate_discord(
        {
            "allowed_mentions": {"parse": []},
            "embeds": [
                {
                    "title": "🗓️ Menù settimanale USI–SUPSI",
                    "url": menu.source_url,
                    "description": (
                        f"**{_week_range(menu)}**\n"
                        "Campus Est · Campus Ovest · SUPSI Mendrisio"
                    ),
                    "color": DISCORD_COLOR,
                    "fields": [_discord_day_field(day) for day in menu.days],
                }
            ],
        }
    )


def render_discord_day(menu: WeeklyMenu, day: DailyMenu) -> dict[str, Any]:
    fields = []
    for item in day.items:
        value_lines = []
        if item.note:
            value_lines.append(f"*{item.note}*")
        prices = (
            ("Studenti", _money(item.prices.students)),
            ("Collaboratori", _money(item.prices.staff)),
            ("Esterni", _money(item.prices.external)),
        )
        rendered_prices = [f"{label}: {value}" for label, value in prices if value]
        if rendered_prices:
            value_lines.append("💸 " + " · ".join(rendered_prices))
        fields.append(
            {
                "name": f"{_emoji(item.category)} {item.category} — {item.name}",
                "value": "\n".join(value_lines) or "—",
                "inline": False,
            }
        )
    embed: dict[str, Any] = {
        "title": f"🍽️ Menù di {day.label} {_date_it(day.date)}",
        "url": menu.source_url,
        "description": (
            f"**{_week_range(menu)}**\n"
            "Campus Est · Campus Ovest · SUPSI Mendrisio"
        ),
        "color": DISCORD_COLOR,
    }
    if fields:
        embed["fields"] = fields
    else:
        embed["description"] += f"\n\n{day.closure_note or 'Chiuso'}"
    return _validate_discord({"allowed_mentions": {"parse": []}, "embeds": [embed]})
