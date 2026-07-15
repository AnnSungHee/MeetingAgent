from agent.llm import LLMAdapter, LLMResponse


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
