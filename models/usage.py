"""Codex 토큰 사용량을 로컬에서 누적하고 조회한다."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4


TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)


def empty_usage() -> dict[str, int]:
    return {field: 0 for field in TOKEN_FIELDS}


def normalize_usage(usage: dict[str, Any] | None) -> dict[str, int]:
    normalized = empty_usage()
    for field in TOKEN_FIELDS:
        value = (usage or {}).get(field, 0)
        normalized[field] = max(0, int(value or 0))
    # cached/reasoning 토큰은 각각 input/output의 부분집합이므로 중복 합산하지 않는다.
    normalized["total_tokens"] = (
        normalized["input_tokens"] + normalized["output_tokens"]
    )
    return normalized


class UsageStore:
    """호출별 사용량과 누적 사용량을 원자적으로 저장한다."""

    _lock = Lock()

    def __init__(self, path: str | Path, budget_tokens: int | None = None) -> None:
        self.path = Path(path)
        self.budget_tokens = budget_tokens

    def start_run(self) -> str:
        run_id = uuid4().hex
        with self._lock:
            data = self._read()
            data["current_run"] = {
                "run_id": run_id,
                "status": "running",
                "started_at": datetime.now().isoformat(),
                "finished_at": None,
                "error": None,
                **normalize_usage(None),
            }
            self._write(data)
        return run_id

    def finish_run(self, run_id: str, usage: dict[str, Any] | None) -> None:
        current_usage = normalize_usage(usage)
        with self._lock:
            data = self._read()
            cumulative = normalize_usage(data.get("cumulative"))
            for field in TOKEN_FIELDS:
                cumulative[field] += current_usage[field]
            cumulative["total_tokens"] = (
                cumulative["input_tokens"] + cumulative["output_tokens"]
            )
            data["cumulative"] = cumulative
            data["current_run"] = {
                "run_id": run_id,
                "status": "completed",
                "started_at": data.get("current_run", {}).get("started_at"),
                "finished_at": datetime.now().isoformat(),
                "error": None,
                **current_usage,
            }
            self._write(data)

    def fail_run(
        self, run_id: str, error: str, usage: dict[str, Any] | None = None
    ) -> None:
        failed_usage = normalize_usage(usage)
        with self._lock:
            data = self._read()
            current = data.get("current_run", {})
            cumulative = normalize_usage(data.get("cumulative"))
            for field in TOKEN_FIELDS:
                cumulative[field] += failed_usage[field]
            cumulative["total_tokens"] = (
                cumulative["input_tokens"] + cumulative["output_tokens"]
            )
            data["cumulative"] = cumulative
            data["current_run"] = {
                "run_id": run_id,
                "status": "failed",
                "started_at": current.get("started_at"),
                "finished_at": datetime.now().isoformat(),
                "error": error,
                **failed_usage,
            }
            self._write(data)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            data = self._read()
        result = deepcopy(data)
        cumulative_total = result["cumulative"]["total_tokens"]
        result["budget_tokens"] = self.budget_tokens
        result["remaining_tokens"] = (
            max(0, self.budget_tokens - cumulative_total)
            if self.budget_tokens is not None
            else None
        )
        result["usage_percent"] = (
            min(100.0, cumulative_total / self.budget_tokens * 100)
            if self.budget_tokens
            else None
        )
        return result

    def _read(self) -> dict[str, Any]:
        default = {
            "version": 1,
            "current_run": {
                "run_id": None,
                "status": "idle",
                "started_at": None,
                "finished_at": None,
                "error": None,
                **normalize_usage(None),
            },
            "cumulative": normalize_usage(None),
        }
        if not self.path.exists():
            return default
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default
        default.update(loaded)
        default["cumulative"] = normalize_usage(default.get("cumulative"))
        return default

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(self.path)
