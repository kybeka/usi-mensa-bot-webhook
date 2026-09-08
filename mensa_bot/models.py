from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True)
class Prices:
    students: Decimal | None = None
    staff: Decimal | None = None
    external: Decimal | None = None


@dataclass(frozen=True)
class MenuItem:
    category: str
    name: str
    note: str | None
    prices: Prices
    dietary_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class DailyMenu:
    date: date
    label: str
    items: tuple[MenuItem, ...]
    closure_note: str | None = None


@dataclass(frozen=True)
class WeeklyMenu:
    week_number: int
    start_date: date
    end_date: date
    source_url: str
    source_last_modified: str | None
    fetched_at: datetime
    venues: tuple[str, ...]
    days: tuple[DailyMenu, ...]

    def menu_for(self, target_date: date) -> DailyMenu | None:
        return next((day for day in self.days if day.date == target_date), None)

    def covers(self, target_date: date) -> bool:
        return self.start_date <= target_date <= self.end_date
