import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.llm import LLMAdapter, LLMResponse
from agent.tools import SAVE_MARKDOWN_TOOL, SAVE_SESSION_SUMMARY_TOOL
from config.settings import settings
from models.usage import UsageStore


def response_with_tools() -> LLMResponse:
    return LLMResponse(
        stop_reason="tool_use",
        content=[
            {"type": "text", "text": "회의록을 저장합니다."},
            {
                "type": "tool_use",
                "id": "call-1",
                "name": "save_session_summary",
                "input": {"participants": []},
            },
        ],
        tool_uses=[
            {
                "type": "tool_use",
                "id": "call-1",
                "name": "save_session_summary",
                "input": {"participants": []},
            }
        ],
    )


def test_append_anthropic_tool_results_uses_content_blocks() -> None:
    adapter = object.__new__(LLMAdapter)
    adapter.provider = "anthropic"
    messages = [{"role": "user", "content": "회의 내용"}]
    results = [{"tool_use_id": "call-1", "content": '{"success": true}'}]

    adapter.append_tool_results(messages, response_with_tools(), results)

    assert messages[-2]["role"] == "assistant"
    assert messages[-1] == {"role": "user", "content": results}


def test_append_anthropic_multiple_tool_results_keeps_all_results() -> None:
    adapter = object.__new__(LLMAdapter)
    adapter.provider = "anthropic"
    response = response_with_tools()
    response.tool_uses.append({
        "type": "tool_use",
        "id": "call-2",
        "name": "save_markdown",
        "input": {"filename": "meeting", "content": "# 회의록"},
    })
    messages: list[dict] = []
    results = [
        {"tool_use_id": "call-1", "content": '{"success": true}'},
        {"tool_use_id": "call-2", "content": '{"success": true}'},
    ]

    adapter.append_tool_results(messages, response, results)

    assert messages[-1]["content"] == results


def test_append_openai_tool_results_uses_tool_messages() -> None:
    adapter = object.__new__(LLMAdapter)
    adapter.provider = "openai"
    messages = [{"role": "user", "content": "회의 내용"}]
    results = [{"tool_use_id": "call-1", "content": '{"success": true}'}]

    adapter.append_tool_results(messages, response_with_tools(), results)

    assistant_message = messages[-2]
    assert assistant_message["role"] == "assistant"
    assert assistant_message["tool_calls"][0]["function"]["name"] == "save_session_summary"
    assert messages[-1] == {
        "role": "tool",
        "tool_call_id": "call-1",
        "content": '{"success": true}',
    }


def test_append_openai_multiple_tool_results_preserves_each_call() -> None:
    adapter = object.__new__(LLMAdapter)
    adapter.provider = "openai"
    response = response_with_tools()
    response.tool_uses.append({
        "type": "tool_use",
        "id": "call-2",
        "name": "save_markdown",
        "input": {"filename": "meeting", "content": "# 회의록"},
    })
    messages: list[dict] = []
    results = [
        {"tool_use_id": "call-1", "content": '{"success": true}'},
        {"tool_use_id": "call-2", "content": '{"success": true}'},
    ]

    adapter.append_tool_results(messages, response, results)

    assert len(messages[0]["tool_calls"]) == 2
    assert [message["tool_call_id"] for message in messages[1:]] == ["call-1", "call-2"]


def test_codex_schema_requires_all_active_tools_and_strips_descriptions() -> None:
    schema = LLMAdapter._codex_output_schema([
        SAVE_SESSION_SUMMARY_TOOL,
        SAVE_MARKDOWN_TOOL,
    ])

    assert schema["required"] == ["save_session_summary", "save_markdown"]
    assert schema["additionalProperties"] is False
    assert "description" not in json.dumps(schema)


def test_parse_codex_events_extracts_final_message_and_usage() -> None:
    output = "\n".join([
        json.dumps({
            "type": "item.completed",
            "item": {"type": "agent_message", "text": '{"ok":true}'},
        }),
        json.dumps({
            "type": "turn.completed",
            "usage": {"input_tokens": 10, "output_tokens": 4},
        }),
    ])

    message, usage, error = LLMAdapter._parse_codex_events(output)

    assert message == '{"ok":true}'
    assert usage == {"input_tokens": 10, "output_tokens": 4}
    assert error is None


def test_codex_adapter_uses_one_cli_call_and_records_usage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = {
        "save_session_summary": {
            "participants": ["홍길동"],
            "overall_summary": "FastAPI를 학습했습니다.",
            "topics_discussed": [],
            "action_items": [],
            "next_week_plan": {"topics": []},
        }
    }
    stdout = "\n".join([
        json.dumps({
            "type": "item.completed",
            "item": {"type": "agent_message", "text": json.dumps(payload)},
        }),
        json.dumps({
            "type": "turn.completed",
            "usage": {"input_tokens": 100, "output_tokens": 25},
        }),
    ])
    calls = []

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    usage_path = tmp_path / "usage.json"
    monkeypatch.setattr("agent.llm.subprocess.run", fake_run)
    monkeypatch.setattr(settings, "codex_command", "codex")
    monkeypatch.setattr(settings, "codex_model", None)
    monkeypatch.setattr(settings, "codex_reasoning_effort", "low")
    monkeypatch.setattr(settings, "token_usage_path", str(usage_path))
    monkeypatch.setattr(settings, "codex_token_budget", 1_000)

    adapter = LLMAdapter(provider="codex")
    response = adapter.chat(
        messages=[{"role": "user", "content": "회의 내용"}],
        tools=[SAVE_SESSION_SUMMARY_TOOL, SAVE_MARKDOWN_TOOL],
        system="사용되지 않는 API provider용 프롬프트",
    )

    assert len(calls) == 1
    assert "--ephemeral" in calls[0][0]
    assert 'model_reasoning_effort="low"' in calls[0][0]
    assert 'model_reasoning_summary="none"' in calls[0][0]
    assert calls[0][1]["input"].startswith("프로그래밍 스터디")
    assert [tool["name"] for tool in response.tool_uses] == [
        "save_session_summary",
        "save_markdown",
    ]
    assert UsageStore(usage_path, 1_000).snapshot()["remaining_tokens"] == 875
