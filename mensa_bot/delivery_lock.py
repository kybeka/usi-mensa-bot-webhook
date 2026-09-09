import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests

LOCK_PREFIX = "menu-delivery"
WORKFLOW_FILE = "send-channel.yml"


class DeliveryLockError(RuntimeError):
    pass


@dataclass(frozen=True)
class LockEvidence:
    kind: str
    url: str


def _github_json(
    session: requests.Session,
    url: str,
    token: str,
    *,
    params: dict[str, object],
) -> dict[str, Any]:
    try:
        response = session.get(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            params=params,
            timeout=30,
        )
    except requests.RequestException as exc:
        raise DeliveryLockError(f"GitHub delivery-lock request failed: {exc}") from exc

    if response.status_code >= 400:
        raise DeliveryLockError(
            f"GitHub delivery-lock request returned HTTP {response.status_code}."
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise DeliveryLockError("GitHub delivery-lock request returned invalid JSON.") from exc
    if not isinstance(data, dict):
        raise DeliveryLockError("GitHub delivery-lock request returned an unexpected payload.")
    return data


def _run_local_date(run: dict[str, Any], timezone: str) -> date | None:
    created_at = run.get("created_at")
    if not isinstance(created_at, str):
        return None
    try:
        timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return timestamp.astimezone(ZoneInfo(timezone)).date()


def find_delivery_lock(
    *,
    repository: str,
    token: str,
    delivery_date: date,
    current_run_id: int,
    timezone: str = "Europe/Zurich",
    api_url: str = "https://api.github.com",
    session: requests.Session | None = None,
) -> LockEvidence | None:
    if repository.count("/") != 1:
        raise DeliveryLockError("GITHUB_REPOSITORY must have the form owner/repository.")
    if not token:
        raise DeliveryLockError("GH_TOKEN is required for the delivery-lock check.")

    client = session or requests.Session()
    repository_url = f"{api_url.rstrip('/')}/repos/{repository}"
    lock_name = f"{LOCK_PREFIX}-{delivery_date.isoformat()}"
    artifacts = _github_json(
        client,
        f"{repository_url}/actions/artifacts",
        token,
        params={"name": lock_name, "per_page": 100},
    ).get("artifacts", [])
    if not isinstance(artifacts, list):
        raise DeliveryLockError("GitHub returned an invalid artifacts list.")
    for artifact in artifacts:
        if isinstance(artifact, dict) and not artifact.get("expired", False):
            return LockEvidence("artifact", str(artifact.get("html_url", "unknown")))

    runs = _github_json(
        client,
        f"{repository_url}/actions/workflows/{WORKFLOW_FILE}/runs",
        token,
        params={"per_page": 100},
    ).get("workflow_runs", [])
    if not isinstance(runs, list):
        raise DeliveryLockError("GitHub returned an invalid workflow-runs list.")

    for run in runs:
        if not isinstance(run, dict) or run.get("id") == current_run_id:
            continue
        event = run.get("event")
        title = str(run.get("display_title", ""))
        is_live_attempt = event == "schedule" or title.endswith("(live)")
        protects_date = run.get("status") != "completed" or run.get("conclusion") == "success"
        if (
            is_live_attempt
            and protects_date
            and _run_local_date(run, timezone) == delivery_date
        ):
            return LockEvidence("workflow_run", str(run.get("html_url", "unknown")))
    return None


def main() -> int:
    try:
        delivery_date = date.fromisoformat(os.environ["DELIVERY_DATE"])
        evidence = find_delivery_lock(
            repository=os.environ.get("GITHUB_REPOSITORY", ""),
            token=os.environ.get("GH_TOKEN", ""),
            delivery_date=delivery_date,
            current_run_id=int(os.environ.get("GITHUB_RUN_ID", "0")),
            timezone=os.environ.get("TIMEZONE", "Europe/Zurich"),
            api_url=os.environ.get("GITHUB_API_URL", "https://api.github.com"),
        )
    except (DeliveryLockError, KeyError, ValueError) as exc:
        print(f"DELIVERY_LOCK_CHECK_FAILED error={exc}")
        return 1

    if evidence is not None:
        print(f"DELIVERY_LOCKED type={evidence.kind} evidence={evidence.url}")
        return 1
    print(f"DELIVERY_LOCK_CLEAR date={delivery_date.isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
