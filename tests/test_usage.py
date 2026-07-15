from pathlib import Path

from models.usage import UsageStore, normalize_usage


def test_total_does_not_double_count_cached_or_reasoning_tokens() -> None:
    usage = normalize_usage({
        "input_tokens": 100,
        "cached_input_tokens": 80,
        "output_tokens": 30,
        "reasoning_output_tokens": 20,
    })

    assert usage["total_tokens"] == 130


def test_usage_store_tracks_current_cumulative_and_remaining(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.json", budget_tokens=1_000)
    run_id = store.start_run()
    assert store.snapshot()["current_run"]["status"] == "running"

    store.finish_run(run_id, {"input_tokens": 100, "output_tokens": 25})
    snapshot = store.snapshot()

    assert snapshot["current_run"]["total_tokens"] == 125
    assert snapshot["cumulative"]["total_tokens"] == 125
    assert snapshot["remaining_tokens"] == 875
    assert snapshot["usage_percent"] == 12.5


def test_failed_run_still_counts_consumed_tokens(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.json", budget_tokens=1_000)
    run_id = store.start_run()
    store.fail_run(
        run_id,
        "invalid structured output",
        {"input_tokens": 40, "output_tokens": 10},
    )

    snapshot = store.snapshot()
    assert snapshot["current_run"]["status"] == "failed"
    assert snapshot["cumulative"]["total_tokens"] == 50
    assert snapshot["remaining_tokens"] == 950
