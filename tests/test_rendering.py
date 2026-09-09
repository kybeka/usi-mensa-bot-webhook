from mensa_bot.rendering import (
    DISCORD_EMBED_TOTAL_LIMIT,
    DISCORD_FIELD_VALUE_LIMIT,
    TELEGRAM_TEXT_LIMIT,
    render_discord_day,
    render_discord_week,
    render_telegram_day,
    render_telegram_week,
)


def test_telegram_messages_are_escaped_and_within_limits(weekly_menu) -> None:
    weekly = render_telegram_week(weekly_menu)
    daily = render_telegram_day(weekly_menu, weekly_menu.days[0])

    assert "Tortilla con patate &amp; cipolle" in weekly
    assert "7–11 settembre 2026 · Settimana 37" in weekly
    assert "Studenti: CHF 10.00" in daily
    assert "7–11 settembre 2026 · Settimana 37" in daily
    assert len(weekly) <= TELEGRAM_TEXT_LIMIT
    assert len(daily) <= TELEGRAM_TEXT_LIMIT


def test_discord_messages_are_within_limits_and_disable_mentions(weekly_menu) -> None:
    for payload in (
        render_discord_week(weekly_menu),
        render_discord_day(weekly_menu, weekly_menu.days[0]),
    ):
        assert payload["allowed_mentions"] == {"parse": []}
        embed = payload["embeds"][0]
        assert "7–11 settembre 2026 · Settimana 37" in embed["description"]
        total = len(embed.get("title", "")) + len(embed.get("description", ""))
        for field in embed.get("fields", []):
            assert len(field["value"]) <= DISCORD_FIELD_VALUE_LIMIT
            total += len(field["name"]) + len(field["value"])
        assert total <= DISCORD_EMBED_TOTAL_LIMIT
