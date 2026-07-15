from agent.renderers import build_output_tool_inputs


SUMMARY = {
    "participants": ["홍길동"],
    "overall_summary": "FastAPI를 학습했습니다.",
    "topics_discussed": [
        {"title": "FastAPI", "summary": "라우팅을 학습함", "decisions": []}
    ],
    "action_items": [{"member": "홍길동", "task": "예제 작성"}],
    "next_week_plan": {"topics": ["Pydantic"]},
}


def test_channel_payloads_are_rendered_from_one_summary() -> None:
    payloads = build_output_tool_inputs(
        SUMMARY,
        ["save_session_summary", "save_markdown", "post_to_slack", "post_to_kakao"],
    )

    assert payloads["save_session_summary"] is SUMMARY
    assert "FastAPI" in payloads["save_markdown"]["content"]
    assert "Pydantic" in payloads["post_to_slack"]["message"]
    assert "*" not in payloads["post_to_kakao"]["message"]
