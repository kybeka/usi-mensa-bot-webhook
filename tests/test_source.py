from datetime import date
from decimal import Decimal

import pytest

from mensa_bot.source import (
    MenuStructureError,
    PublishedWeekMismatch,
    parse_date_range,
    parse_weekly_menu,
    require_current_week,
)


def test_parses_compact_and_cross_month_ranges() -> None:
    assert parse_date_range("07-11.09.2026") == (
        date(2026, 9, 7),
        date(2026, 9, 11),
    )
    assert parse_date_range("28.09-02.10.2026") == (
        date(2026, 9, 28),
        date(2026, 10, 2),
    )
    assert parse_date_range("29.12.2025-02.01.2026") == (
        date(2025, 12, 29),
        date(2026, 1, 2),
    )


def test_parses_only_the_italian_tab_group(fixture_html: str) -> None:
    menu = parse_weekly_menu(fixture_html)

    assert menu.week_number == 37
    assert len(menu.days) == 5
    assert menu.days[0].label == "Lunedì"
    assert menu.days[0].items[0].name == "Tortilla con patate & cipolle"
    assert menu.days[0].items[0].dietary_tags == ("vegetarian",)
    assert menu.days[0].items[0].prices.students == Decimal("10.00")
    assert menu.days[1].items[0].dietary_tags == ("vegan",)
    assert all(item.name != "Must not be parsed" for day in menu.days for item in day.items)


def test_rejects_a_stale_published_week(weekly_menu) -> None:
    with pytest.raises(PublishedWeekMismatch, match="does not cover"):
        require_current_week(weekly_menu, date(2026, 9, 14))


def test_rejects_missing_weekday_panel(fixture_html: str) -> None:
    broken = fixture_html.replace(
        '<div id="tab5" class="pwr-tabs__content">',
        '<div id="removed" class="not-a-tab">',
        1,
    )
    with pytest.raises(MenuStructureError, match="Expected 5"):
        parse_weekly_menu(broken)


def test_rejects_empty_day_without_closure_notice(fixture_html: str) -> None:
    broken = fixture_html.replace(
        '<section class="menu-section">\n              <div class="menu-category-tag">DESSERT</div>\n              <div class="menu-item"><h3>Dessert del giorno</h3><p class="menu-price">Studenti: CHF 3.50</p></div>\n            </section>',
        "",
        1,
    )
    with pytest.raises(MenuStructureError, match="Venerdì has no menu items"):
        parse_weekly_menu(broken)
