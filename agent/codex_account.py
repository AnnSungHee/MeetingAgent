"""Codex App Server에서 실제 ChatGPT 계정 한도와 사용량을 조회한다."""

from __future__ import annotations

from datetime import datetime
import json
import selectors
import subprocess
from threading import Lock
import time
from typing import Any

from config.settings import settings


class CodexAccountMonitor:
    """App Server 조회 결과를 캐시해 대시보드 폴링 비용을 제한한다."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._cached: dict[str, Any] | None = None
        self._cached_at = 0.0

    def snapshot(self, force: bool = False) -> dict[str, Any]:
        if not settings.codex_account_usage_enabled:
            return self._unavailable("계정 사용량 조회가 비활성화되어 있습니다.")
        with self._lock:
            now = time.monotonic()
            if (
                not force
                and self._cached is not None
                and now - self._cached_at < settings.codex_account_cache_seconds
            ):
                return self._cached
            try:
                rate_limits, token_usage = self._query_app_server()
                self._cached = self._normalize(rate_limits, token_usage)
            except Exception as exc:
                self._cached = self._unavailable(str(exc))
            self._cached_at = now
            return self._cached

    def _query_app_server(self) -> tuple[dict[str, Any], dict[str, Any]]:
        process = subprocess.Popen(
            [settings.codex_command, "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        if process.stdin is None or process.stdout is None:
            raise RuntimeError("Codex App Server 파이프를 열 수 없습니다.")

        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        try:
            self._send(process, {
                "method": "initialize",
                "id": 0,
                "params": {
                    "clientInfo": {
                        "name": "meeting_agent",
                        "title": "MeetingAgent",
                        "version": "0.1.0",
                    }
                },
            })
            initialized = self._wait_for_ids(process, selector, {0})
            self._result_or_raise(initialized[0])
            self._send(process, {"method": "initialized", "params": {}})
            self._send(process, {"method": "account/rateLimits/read", "id": 1})
            self._send(process, {"method": "account/usage/read", "id": 2})
            responses = self._wait_for_ids(process, selector, {1, 2})
            rate_limits = self._result_or_raise(responses[1])
            # 일부 계정에서는 token activity summary가 제공되지 않아도 한도는 표시한다.
            token_usage = responses[2].get("result") or {}
            return rate_limits, token_usage
        finally:
            selector.close()
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)

    @staticmethod
    def _send(process: subprocess.Popen[str], message: dict[str, Any]) -> None:
        assert process.stdin is not None
        process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        process.stdin.flush()

    @staticmethod
    def _wait_for_ids(
        process: subprocess.Popen[str],
        selector: selectors.BaseSelector,
        expected_ids: set[int],
    ) -> dict[int, dict[str, Any]]:
        deadline = time.monotonic() + settings.codex_account_timeout_seconds
        responses: dict[int, dict[str, Any]] = {}
        while expected_ids - responses.keys():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Codex 계정 사용량 조회 시간이 초과되었습니다.")
            if not selector.select(timeout=remaining):
                raise TimeoutError("Codex 계정 사용량 응답이 없습니다.")
            assert process.stdout is not None
            line = process.stdout.readline()
            if not line:
                raise RuntimeError(
                    f"Codex App Server가 종료되었습니다 (code={process.poll()})."
                )
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            response_id = message.get("id")
            if response_id not in expected_ids:
                continue
            responses[int(response_id)] = message
        return responses

    @staticmethod
    def _result_or_raise(message: dict[str, Any]) -> dict[str, Any]:
        if "error" in message:
            raise RuntimeError(f"Codex App Server 오류: {message['error']}")
        return message.get("result") or {}

    @classmethod
    def _normalize(
        cls, rate_response: dict[str, Any], usage_response: dict[str, Any]
    ) -> dict[str, Any]:
        snapshots = rate_response.get("rateLimitsByLimitId")
        if not snapshots:
            fallback = rate_response.get("rateLimits") or {}
            snapshots = {fallback.get("limitId") or "codex": fallback}

        limits = []
        plan_type = None
        for limit_id, snapshot in snapshots.items():
            plan_type = plan_type or snapshot.get("planType")
            for window_name in ("primary", "secondary"):
                window = snapshot.get(window_name)
                if not window:
                    continue
                used = max(0, min(100, int(window.get("usedPercent", 0))))
                duration = window.get("windowDurationMins")
                limits.append({
                    "limit_id": limit_id,
                    "limit_name": snapshot.get("limitName"),
                    "window": window_name,
                    "label": cls._window_label(duration, window_name),
                    "used_percent": used,
                    "remaining_percent": 100 - used,
                    "window_duration_mins": duration,
                    "resets_at": window.get("resetsAt"),
                    "rate_limit_reached_type": snapshot.get("rateLimitReachedType"),
                })

        return {
            "available": True,
            "error": None,
            "fetched_at": datetime.now().isoformat(),
            "plan_type": plan_type,
            "limits": limits,
            "usage": usage_response.get("summary") or {},
            "daily_usage_buckets": usage_response.get("dailyUsageBuckets") or [],
            "reset_credits": rate_response.get("rateLimitResetCredits"),
        }

    @staticmethod
    def _window_label(duration: Any, window_name: str) -> str:
        if duration == 300:
            return "5시간 한도"
        if duration == 10_080:
            return "주간 한도"
        if isinstance(duration, int) and duration > 0:
            if duration % 1_440 == 0:
                return f"{duration // 1_440}일 한도"
            if duration % 60 == 0:
                return f"{duration // 60}시간 한도"
            return f"{duration}분 한도"
        return "주 한도" if window_name == "secondary" else "기본 한도"

    @staticmethod
    def _unavailable(error: str) -> dict[str, Any]:
        return {
            "available": False,
            "error": error,
            "fetched_at": datetime.now().isoformat(),
            "plan_type": None,
            "limits": [],
            "usage": {},
            "daily_usage_buckets": [],
            "reset_credits": None,
        }


account_monitor = CodexAccountMonitor()
