import os
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from .models import WeeklyMenu
from .source import (
    DEFAULT_MENU_URL,
    FetchedMenuPage,
    MenuError,
    MenuFetchError,
    PublishedWeekMismatch,
    fetch_menu_page,
    parse_weekly_menu,
    require_current_week,
)


@dataclass(frozen=True)
class SnapshotOutcome:
    source: str
    menu: WeeklyMenu
    path: Path


def _fetch_with_retry(
    url: str,
    *,
    timeout_seconds: float,
    retries: int,
    backoff_seconds: float,
    fetcher: Callable[..., FetchedMenuPage],
    sleep: Callable[[float], None],
) -> FetchedMenuPage:
    last_error: MenuFetchError | None = None
    for attempt in range(1, retries + 1):
        try:
            return fetcher(url, timeout_seconds=timeout_seconds)
        except MenuFetchError as exc:
            last_error = exc
            if attempt == retries:
                break
            delay = backoff_seconds * attempt
            print(
                f"WARN snapshot_fetch attempt={attempt}/{retries} "
                f"retry_in_seconds={delay:g} error={exc}"
            )
            sleep(delay)
    raise MenuFetchError(f"Menu snapshot fetch failed after {retries} attempts: {last_error}")


def _read_cached_menu(path: Path, *, source_url: str) -> WeeklyMenu:
    try:
        html = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MenuFetchError(f"Could not read cached menu snapshot {path}: {exc}") from exc
    return parse_weekly_menu(html, source_url=source_url)


def _write_snapshot(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(html, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_menu_snapshot(
    target_date: date,
    snapshot_path: Path,
    *,
    source_url: str = DEFAULT_MENU_URL,
    timeout_seconds: float = 30,
    retries: int = 3,
    backoff_seconds: float = 3,
    fetcher: Callable[..., FetchedMenuPage] = fetch_menu_page,
    sleep: Callable[[float], None] = time.sleep,
) -> SnapshotOutcome:
    if retries < 1:
        raise RuntimeError("SNAPSHOT_FETCH_RETRIES must be at least 1.")

    page = _fetch_with_retry(
        source_url,
        timeout_seconds=timeout_seconds,
        retries=retries,
        backoff_seconds=backoff_seconds,
        fetcher=fetcher,
        sleep=sleep,
    )
    live_menu = parse_weekly_menu(
        page.html,
        source_url=source_url,
        source_last_modified=page.last_modified,
    )

    try:
        require_current_week(live_menu, target_date)
    except PublishedWeekMismatch as live_error:
        try:
            cached_menu = _read_cached_menu(snapshot_path, source_url=source_url)
            require_current_week(cached_menu, target_date)
        except MenuError as cache_error:
            raise PublishedWeekMismatch(
                f"{live_error} No valid cached menu covers {target_date.isoformat()}: "
                f"{cache_error}"
            ) from cache_error
        print(
            f"SNAPSHOT_RESULT source=cache target_date={target_date.isoformat()} "
            f"live_range={live_menu.start_date.isoformat()}..{live_menu.end_date.isoformat()} "
            f"cached_range={cached_menu.start_date.isoformat()}..{cached_menu.end_date.isoformat()}"
        )
        return SnapshotOutcome("cache", cached_menu, snapshot_path)

    _write_snapshot(snapshot_path, page.html)
    print(
        f"SNAPSHOT_RESULT source=live target_date={target_date.isoformat()} "
        f"range={live_menu.start_date.isoformat()}..{live_menu.end_date.isoformat()}"
    )
    return SnapshotOutcome("live", live_menu, snapshot_path)


def main() -> int:
    try:
        target_text = os.getenv("DELIVERY_DATE", "").strip()
        snapshot_text = os.getenv("MENU_SNAPSHOT_PATH", "").strip()
        if not target_text or not snapshot_text:
            raise RuntimeError("DELIVERY_DATE and MENU_SNAPSHOT_PATH are required.")

        prepare_menu_snapshot(
            date.fromisoformat(target_text),
            Path(snapshot_text),
            source_url=os.getenv("MENU_URL", DEFAULT_MENU_URL).strip() or DEFAULT_MENU_URL,
            timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30")),
            retries=int(os.getenv("SNAPSHOT_FETCH_RETRIES", "3")),
            backoff_seconds=float(os.getenv("SNAPSHOT_RETRY_BACKOFF_SECONDS", "3")),
        )
        return 0
    except (MenuError, OSError, RuntimeError, ValueError) as exc:
        print(f"SNAPSHOT_FAILED error={exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
