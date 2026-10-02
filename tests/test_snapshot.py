from datetime import date

import pytest

from mensa_bot.snapshot import prepare_menu_snapshot
from mensa_bot.source import FetchedMenuPage, MenuFetchError, PublishedWeekMismatch


def _fetcher(html: str):
    def fetch(url: str, *, timeout_seconds: float) -> FetchedMenuPage:
        assert url == "https://menu.example/menu"
        assert timeout_seconds == 12
        return FetchedMenuPage(html, "Fri, 02 Oct 2026 08:00:00 GMT")

    return fetch


def _following_week(html: str) -> str:
    return html.replace("07-11.09.2026", "14-18.09.2026").replace(
        "SETTIMANA 37", "SETTIMANA 38"
    )


def test_saves_a_valid_live_week(fixture_html: str, tmp_path) -> None:
    snapshot = tmp_path / "menu-cache" / "current-week.html"

    outcome = prepare_menu_snapshot(
        date(2026, 9, 11),
        snapshot,
        source_url="https://menu.example/menu",
        timeout_seconds=12,
        fetcher=_fetcher(fixture_html),
    )

    assert outcome.source == "live"
    assert outcome.menu.week_number == 37
    assert snapshot.read_text(encoding="utf-8") == fixture_html


def test_uses_cached_current_week_when_live_page_rolls_forward(
    fixture_html: str, tmp_path
) -> None:
    snapshot = tmp_path / "current-week.html"
    snapshot.write_text(fixture_html, encoding="utf-8")

    outcome = prepare_menu_snapshot(
        date(2026, 9, 11),
        snapshot,
        source_url="https://menu.example/menu",
        timeout_seconds=12,
        fetcher=_fetcher(_following_week(fixture_html)),
    )

    assert outcome.source == "cache"
    assert outcome.menu.week_number == 37
    assert snapshot.read_text(encoding="utf-8") == fixture_html


def test_rejects_a_future_live_week_without_a_valid_cache(
    fixture_html: str, tmp_path
) -> None:
    with pytest.raises(PublishedWeekMismatch, match="No valid cached menu"):
        prepare_menu_snapshot(
            date(2026, 9, 11),
            tmp_path / "missing.html",
            source_url="https://menu.example/menu",
            timeout_seconds=12,
            fetcher=_fetcher(_following_week(fixture_html)),
        )


def test_rejects_an_invalid_cached_snapshot(fixture_html: str, tmp_path) -> None:
    snapshot = tmp_path / "current-week.html"
    snapshot.write_text("not a menu", encoding="utf-8")

    with pytest.raises(PublishedWeekMismatch, match="No valid cached menu"):
        prepare_menu_snapshot(
            date(2026, 9, 11),
            snapshot,
            source_url="https://menu.example/menu",
            timeout_seconds=12,
            fetcher=_fetcher(_following_week(fixture_html)),
        )


def test_retries_a_transient_fetch_failure(fixture_html: str, tmp_path) -> None:
    attempts = 0
    delays: list[float] = []

    def fetch(url: str, *, timeout_seconds: float) -> FetchedMenuPage:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise MenuFetchError("temporary failure")
        return FetchedMenuPage(fixture_html, None)

    outcome = prepare_menu_snapshot(
        date(2026, 9, 11),
        tmp_path / "current-week.html",
        source_url="https://menu.example/menu",
        timeout_seconds=12,
        retries=2,
        backoff_seconds=2,
        fetcher=fetch,
        sleep=delays.append,
    )

    assert outcome.source == "live"
    assert attempts == 2
    assert delays == [2]
