from pathlib import Path

import pytest

from agent.core import MeetingAgent
from agent.llm import LLMResponse
from config.settings import settings


SUMMARY_INPUT = {
    "participants": ["홍길동"],
    "overall_summary": "FastAPI를 학습했습니다.",
    "topics_discussed": [{"title": "FastAPI", "summary": "라우팅을 학습함"}],
    "action_items": [],
    "next_week_plan": {"topics": ["Pydantic"]},
}


class FakeAdapter:
    def __init__(self, responses: list[LLMResponse]) -> None:
        self.responses = responses
        self.appended: list[list[dict]] = []

    def chat(self, **_: object) -> LLMResponse:
        return self.responses.pop(0)

    def append_tool_results(
        self, messages: list[dict], _: LLMResponse, results: list[dict]
    ) -> None:
        self.appended.append(results)
        messages.append({"role": "user", "content": "tool results"})


class SingleCallFakeAdapter(FakeAdapter):
    requires_tool_result_roundtrip = False


def tool_response(*tool_uses: dict) -> LLMResponse:
    return LLMResponse(
        stop_reason="tool_use",
        content=list(tool_uses),
        tool_uses=list(tool_uses),
    )


def tool(tool_id: str, name: str, tool_input: dict) -> dict:
    return {"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}


def end_response() -> LLMResponse:
    return LLMResponse(stop_reason="end_turn", content=[], tool_uses=[])


@pytest.fixture
def configured_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "max_agent_iterations", 5)
    monkeypatch.setattr(type(settings), "validate_runtime", lambda _self, _: None)


def make_agent(fake: FakeAdapter) -> MeetingAgent:
    agent = MeetingAgent.__new__(MeetingAgent)
    agent.llm = fake
    return agent


def test_agent_persists_summary_and_reports_failed_output(
    configured_settings: None,
) -> None:
    fake = FakeAdapter([
        tool_response(tool("summary", "save_session_summary", SUMMARY_INPUT)),
        tool_response(tool("markdown", "save_markdown", {"filename": "note", "content": "# 회의록"})),
        end_response(),
    ])
    agent = make_agent(fake)
    agent._execute_tool = lambda name, _: (
        {"success": False, "error": "temporary outage"}
        if name == "save_markdown"
        else agent._save_session_summary(SUMMARY_INPUT)
    )

    session = agent.run(supplementary_text="회의 내용", output_overrides=["markdown"])

    assert session.output_results[0].channel == "markdown"
    assert session.output_results[0].success is False
    assert list(Path(settings.data_dir).glob("*.json"))


def test_output_before_summary_is_rejected_but_other_tools_continue(
    configured_settings: None,
) -> None:
    fake = FakeAdapter([
        tool_response(
            tool("markdown", "save_markdown", {"filename": "note", "content": "# 회의록"}),
            tool("summary", "save_session_summary", SUMMARY_INPUT),
        ),
        end_response(),
    ])

    session = make_agent(fake).run(
        supplementary_text="회의 내용", output_overrides=["markdown"]
    )

    assert session.output_results[0].success is False
    assert "저장하기 전에" not in session.output_results[0].error
    assert "save_session_summary" in session.output_results[0].error


def test_missing_requested_output_raises_error(configured_settings: None) -> None:
    fake = FakeAdapter([
        tool_response(tool("summary", "save_session_summary", SUMMARY_INPUT)),
        end_response(),
    ])

    with pytest.raises(RuntimeError, match="출력 도구가 호출되지 않았습니다"):
        make_agent(fake).run(supplementary_text="회의 내용", output_overrides=["markdown"])


def test_invalid_summary_input_returns_validation_error() -> None:
    agent = MeetingAgent.__new__(MeetingAgent)
    invalid = {key: value for key, value in SUMMARY_INPUT.items() if key != "topics_discussed"}

    result = agent._execute_tool("save_session_summary", invalid)

    assert result["success"] is False
    assert "topics_discussed" in result["error"]


def test_session_ids_are_unique() -> None:
    agent = MeetingAgent.__new__(MeetingAgent)

    first = agent._save_session_summary(SUMMARY_INPUT)["session"].session_id
    second = agent._save_session_summary(SUMMARY_INPUT)["session"].session_id

    assert first != second


def test_single_call_adapter_skips_tool_result_roundtrip(
    configured_settings: None,
) -> None:
    fake = SingleCallFakeAdapter([
        tool_response(
            tool("summary", "save_session_summary", SUMMARY_INPUT),
            tool(
                "markdown",
                "save_markdown",
                {"filename": "note", "content": "# 회의록"},
            ),
        ),
    ])

    session = make_agent(fake).run(
        supplementary_text="회의 내용", output_overrides=["markdown"]
    )

    assert session.overall_summary == SUMMARY_INPUT["overall_summary"]
    assert fake.appended == []
