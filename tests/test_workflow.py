from pathlib import Path


WORKFLOW = Path(".github/workflows/send-channel.yml")


def test_live_payload_validation_runs_in_dry_run_mode_before_the_lock() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    validation = workflow.index("- name: Validate the live payload before acquiring the lock")
    lock = workflow.index("- name: Check the per-day delivery lock")
    validation_block = workflow[validation:lock]

    assert validation < lock
    assert "if: github.event_name == 'schedule' || inputs.delivery_mode == 'live'" in validation_block
    assert "DELIVERY_MODE: dry-run" in validation_block
