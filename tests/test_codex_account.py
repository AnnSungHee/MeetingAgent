from agent.codex_account import CodexAccountMonitor
from config.settings import settings


RATE_LIMITS = {
    "rateLimits": {
        "limitId": "codex",
        "planType": "plus",
        "primary": {
            "usedPercent": 25,
            "windowDurationMins": 300,
            "resetsAt": 1_800_000_000,
        },
        "secondary": {
            "usedPercent": 40,
            "windowDurationMins": 10_080,
            "resetsAt": 1_800_100_000,
        },
    }
}


def test_account_monitor_normalizes_real_remaining_percent() -> None:
    result = CodexAccountMonitor._normalize(
        RATE_LIMITS,
        {"summary": {"lifetimeTokens": 123_456}},
    )

    assert result["available"] is True
    assert result["plan_type"] == "plus"
    assert [limit["label"] for limit in result["limits"]] == [
        "5시간 한도",
        "주간 한도",
    ]
    assert [limit["remaining_percent"] for limit in result["limits"]] == [75, 60]
    assert result["usage"]["lifetimeTokens"] == 123_456


def test_account_monitor_caches_app_server_query(monkeypatch) -> None:
    monitor = CodexAccountMonitor()
    calls = []
    monkeypatch.setattr(settings, "codex_account_usage_enabled", True)
    monkeypatch.setattr(settings, "codex_account_cache_seconds", 30)
    monkeypatch.setattr(
        monitor,
        "_query_app_server",
        lambda: calls.append(True) or (RATE_LIMITS, {"summary": {}}),
    )

    first = monitor.snapshot()
    second = monitor.snapshot()

    assert first is second
    assert len(calls) == 1


def test_account_monitor_falls_back_on_app_server_error(monkeypatch) -> None:
    monitor = CodexAccountMonitor()
    monkeypatch.setattr(settings, "codex_account_usage_enabled", True)

    def fail():
        raise RuntimeError("not logged in")

    monkeypatch.setattr(monitor, "_query_app_server", fail)
    result = monitor.snapshot(force=True)

    assert result["available"] is False
    assert "not logged in" in result["error"]
