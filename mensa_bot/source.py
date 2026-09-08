import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

import requests
from bs4 import BeautifulSoup, Tag

from .models import DailyMenu, MenuItem, Prices, WeeklyMenu

DEFAULT_MENU_URL = "https://menu.1908.ch/usi-supsi"
VENUES = (
    "Campus Est USI SUPSI Viganello",
    "Campus Ovest USI Lugano",
    "Campus SUPSI Mendrisio",
)
ITALIAN_WEEKDAYS = ("Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì")
DATE_RANGE_RE = re.compile(
    r"(?P<start_day>\d{1,2})"
    r"(?:\.(?P<start_month>\d{1,2}))?"
    r"(?:\.(?P<start_year>\d{4}))?"
    r"\s*[-–]\s*"
    r"(?P<end_day>\d{1,2})\.(?P<end_month>\d{1,2})\.(?P<end_year>\d{4})"
)
WEEK_NUMBER_RE = re.compile(r"SETTIMANA\s+(\d{1,2})", re.IGNORECASE)
PRICE_RE = re.compile(
    r"^(Studenti|Collaboratori|Esterni):\s*CHF\s*([\d.,]+)$",
    re.IGNORECASE,
)
CLOSED_RE = re.compile(r"\b(chiuso|chiusa|festa|festivo|ferie)\b", re.IGNORECASE)


class MenuError(RuntimeError):
    """Base class for failures that must prevent publication."""


class MenuFetchError(MenuError):
    pass


class MenuStructureError(MenuError):
    pass


class PublishedWeekMismatch(MenuError):
    pass


def _text(node: Tag | None) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


def parse_date_range(value: str) -> tuple[date, date]:
    match = DATE_RANGE_RE.search(value)
    if not match:
        raise MenuStructureError(f"Could not parse published date range: {value!r}")

    end_year = int(match.group("end_year"))
    end_month = int(match.group("end_month"))
    start_month = int(match.group("start_month") or end_month)
    start_year_text = match.group("start_year")
    start_year = int(start_year_text) if start_year_text else end_year
    if not start_year_text and start_month > end_month:
        start_year -= 1

    try:
        start = date(start_year, start_month, int(match.group("start_day")))
        end = date(end_year, end_month, int(match.group("end_day")))
    except ValueError as exc:
        raise MenuStructureError(f"Invalid published date range: {value!r}") from exc

    if end - start != timedelta(days=4) or start.weekday() != 0 or end.weekday() != 4:
        raise MenuStructureError(
            f"Expected a Monday-Friday range, received {start.isoformat()} to {end.isoformat()}."
        )
    return start, end


def _parse_price(value: str) -> tuple[str, Decimal]:
    match = PRICE_RE.match(value)
    if not match:
        raise MenuStructureError(f"Unrecognized price: {value!r}")
    try:
        amount = Decimal(match.group(2).replace(",", "."))
    except InvalidOperation as exc:
        raise MenuStructureError(f"Invalid CHF amount: {value!r}") from exc
    return match.group(1).casefold(), amount


def _dietary_tags(category: str) -> tuple[str, ...]:
    normalized = category.casefold()
    if normalized.startswith("vegano"):
        return ("vegan",)
    if normalized.startswith("vegetariano"):
        return ("vegetarian",)
    return ()


def _parse_item(section: Tag) -> MenuItem:
    category = _text(section.select_one(".menu-category-tag"))
    name = _text(section.select_one(".menu-item h3"))
    note = _text(section.select_one(".menu-note")) or None
    if not category or not name:
        raise MenuStructureError("A menu section is missing its category or dish name.")

    values: dict[str, Decimal] = {}
    for price_node in section.select(".menu-price"):
        label, amount = _parse_price(_text(price_node))
        values[label] = amount
    if not values:
        raise MenuStructureError(f"No recognized prices found for {name!r}.")

    return MenuItem(
        category=category,
        name=name,
        note=note,
        prices=Prices(
            students=values.get("studenti"),
            staff=values.get("collaboratori"),
            external=values.get("esterni"),
        ),
        dietary_tags=_dietary_tags(category),
    )


def _find_italian_heading(soup: BeautifulSoup) -> Tag:
    for heading in soup.find_all("h1"):
        if WEEK_NUMBER_RE.search(_text(heading)):
            return heading
    raise MenuStructureError("Italian weekly-menu heading was not found.")


def parse_weekly_menu(
    html: str,
    *,
    source_url: str = DEFAULT_MENU_URL,
    source_last_modified: str | None = None,
    fetched_at: datetime | None = None,
) -> WeeklyMenu:
    soup = BeautifulSoup(html, "html.parser")
    heading = _find_italian_heading(soup)
    week_match = WEEK_NUMBER_RE.search(_text(heading))
    if week_match is None:
        raise MenuStructureError("Published week number was not found.")

    date_node = heading.parent.select_one(".pwr-sec__title-intro") if heading.parent else None
    start_date, end_date = parse_date_range(_text(date_node))
    week_number = int(week_match.group(1))
    if week_number != start_date.isocalendar().week:
        raise MenuStructureError(
            f"Week number {week_number} does not match the published range starting {start_date}."
        )

    tabs = heading.find_next("div", class_="pwr-tabs")
    if not isinstance(tabs, Tag):
        raise MenuStructureError("Italian weekday tabs were not found.")

    tab_labels = tuple(_text(node) for node in tabs.select(".pwr-tabs__header li.pwr-tabs__tab"))
    if tab_labels != ITALIAN_WEEKDAYS:
        raise MenuStructureError(f"Unexpected Italian weekday tabs: {tab_labels!r}")

    panels = tabs.select(".pwr-tabs__body > .pwr-tabs__content")
    if len(panels) != 5:
        raise MenuStructureError(f"Expected 5 Italian weekday panels, found {len(panels)}.")

    days: list[DailyMenu] = []
    for index, (label, panel) in enumerate(zip(tab_labels, panels, strict=True)):
        items = tuple(_parse_item(section) for section in panel.select(".menu-section"))
        closure_note = None
        if not items:
            panel_text = _text(panel)
            closed_match = CLOSED_RE.search(panel_text)
            if not closed_match:
                raise MenuStructureError(f"{label} has no menu items and no closure notice.")
            closure_note = panel_text
        days.append(
            DailyMenu(
                date=start_date + timedelta(days=index),
                label=label,
                items=items,
                closure_note=closure_note,
            )
        )

    return WeeklyMenu(
        week_number=week_number,
        start_date=start_date,
        end_date=end_date,
        source_url=source_url,
        source_last_modified=source_last_modified,
        fetched_at=fetched_at or datetime.now(timezone.utc),
        venues=VENUES,
        days=tuple(days),
    )


def fetch_weekly_menu(
    url: str = DEFAULT_MENU_URL,
    *,
    timeout_seconds: float = 30,
    session: requests.Session | None = None,
) -> WeeklyMenu:
    client = session or requests.Session()
    try:
        response = client.get(
            url,
            timeout=timeout_seconds,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "it-CH,it;q=0.9",
                "User-Agent": "usi-mensa-bot/2.0 (+https://github.com/kybeka/usi-mensa-bot-webhook)",
            },
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise MenuFetchError(f"Could not fetch the 1908 menu: {exc}") from exc

    return parse_weekly_menu(
        response.text,
        source_url=url,
        source_last_modified=response.headers.get("Last-Modified"),
    )


def require_current_week(menu: WeeklyMenu, target_date: date) -> None:
    if not menu.covers(target_date):
        raise PublishedWeekMismatch(
            f"1908 currently publishes {menu.start_date.isoformat()} to {menu.end_date.isoformat()}, "
            f"which does not cover {target_date.isoformat()}."
        )
    if menu.menu_for(target_date) is None:
        raise PublishedWeekMismatch(f"No weekday panel exists for {target_date.isoformat()}.")
