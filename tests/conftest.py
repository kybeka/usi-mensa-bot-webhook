from pathlib import Path

import pytest

from mensa_bot.models import WeeklyMenu
from mensa_bot.source import parse_weekly_menu


@pytest.fixture
def fixture_html() -> str:
    path = Path(__file__).parent / "fixtures" / "usi_supsi_week.html"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def weekly_menu(fixture_html: str) -> WeeklyMenu:
    return parse_weekly_menu(fixture_html)
