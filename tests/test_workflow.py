from pathlib import Path


WORKFLOW = Path(".github/workflows/send-channel.yml")


def test_schedule_avoids_peak_load_and_uses_zurich_time() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    schedule = workflow.index("  schedule:")
    permissions = workflow.index("permissions:")
    schedule_block = workflow[schedule:permissions]

    assert "cron: '17 7 * * 1-5'" in schedule_block
    assert "timezone: Europe/Zurich" in schedule_block


def test_live_payload_validation_runs_in_dry_run_mode_before_the_lock() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    restore = workflow.index("- name: Restore the newest current-week menu snapshot")
    prepare = workflow.index("- name: Prepare the current-week menu snapshot")
    validation = workflow.index("- name: Validate the live payload before acquiring the lock")
    save = workflow.index("- name: Save the current-week menu snapshot")
    lock = workflow.index("- name: Check the per-day delivery lock")
    validation_block = workflow[validation:lock]

    assert restore < prepare < validation < save < lock
    assert "if: github.event_name == 'schedule' || inputs.delivery_mode == 'live'" in validation_block
    assert "DELIVERY_MODE: dry-run" in validation_block
    assert "MENU_SNAPSHOT_PATH: menu-cache/current-week.html" in validation_block


def test_live_delivery_uses_a_daily_cache_key_and_the_validated_snapshot() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    send = workflow.index("- name: Send channel menu")
    send_block = workflow[send:]

    assert "uses: actions/cache/restore@v6" in workflow
    assert "uses: actions/cache/save@v6" in workflow
    assert "menu-snapshot-${{ steps.delivery-date.outputs.week_key }}-${{ steps.delivery-date.outputs.date }}" in workflow
    assert "restore-keys:" in workflow
    assert "MENU_SNAPSHOT_PATH: ${{ (github.event_name == 'schedule' || inputs.delivery_mode == 'live')" in send_block
