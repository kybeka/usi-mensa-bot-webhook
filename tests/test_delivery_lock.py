from datetime import date

from mensa_bot.delivery_lock import find_delivery_lock


class FakeResponse:
    def __init__(self, body: dict, status_code: int = 200) -> None:
        self.status_code = status_code
        self._body = body

    def json(self) -> dict:
        return self._body


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.gets: list[tuple[str, dict[str, object]]] = []

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, object],
        timeout: int,
    ) -> FakeResponse:
        self.gets.append((url, params))
        return self.responses.pop(0)


def test_existing_artifact_locks_delivery() -> None:
    session = FakeSession(
        [
            FakeResponse(
                {
                    "artifacts": [
                        {
                            "expired": False,
                            "html_url": "https://github.example/artifacts/1",
                        }
                    ]
                }
            )
        ]
    )

    evidence = find_delivery_lock(
        repository="owner/repository",
        token="token",
        delivery_date=date(2026, 9, 9),
        current_run_id=200,
        session=session,
    )

    assert evidence is not None
    assert evidence.kind == "artifact"


def test_successful_scheduled_run_locks_legacy_delivery() -> None:
    session = FakeSession(
        [
            FakeResponse({"artifacts": []}),
            FakeResponse(
                {
                    "workflow_runs": [
                        {
                            "id": 100,
                            "event": "schedule",
                            "status": "completed",
                            "conclusion": "success",
                            "display_title": "Send 1908 menu",
                            "created_at": "2026-09-09T09:26:37Z",
                            "html_url": "https://github.example/runs/100",
                        }
                    ]
                }
            ),
        ]
    )

    evidence = find_delivery_lock(
        repository="owner/repository",
        token="token",
        delivery_date=date(2026, 9, 9),
        current_run_id=200,
        session=session,
    )

    assert evidence is not None
    assert evidence.kind == "workflow_run"


def test_failed_and_dry_run_attempts_do_not_lock_delivery() -> None:
    session = FakeSession(
        [
            FakeResponse({"artifacts": []}),
            FakeResponse(
                {
                    "workflow_runs": [
                        {
                            "id": 100,
                            "event": "schedule",
                            "status": "completed",
                            "conclusion": "failure",
                            "display_title": "Send 1908 menu (live)",
                            "created_at": "2026-09-09T07:00:00Z",
                        },
                        {
                            "id": 101,
                            "event": "workflow_dispatch",
                            "status": "completed",
                            "conclusion": "success",
                            "display_title": "Send 1908 menu (dry-run)",
                            "created_at": "2026-09-09T08:00:00Z",
                        },
                        {
                            "id": 102,
                            "event": "schedule",
                            "status": "completed",
                            "conclusion": "success",
                            "display_title": "Send 1908 menu (live)",
                            "created_at": "2026-09-08T08:00:00Z",
                        },
                        {
                            "id": 200,
                            "event": "workflow_dispatch",
                            "status": "in_progress",
                            "conclusion": None,
                            "display_title": "Send 1908 menu (live)",
                            "created_at": "2026-09-09T09:00:00Z",
                        },
                    ]
                }
            ),
        ]
    )

    evidence = find_delivery_lock(
        repository="owner/repository",
        token="token",
        delivery_date=date(2026, 9, 9),
        current_run_id=200,
        session=session,
    )

    assert evidence is None
