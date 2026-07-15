"""
LLM 어댑터: Claude(Anthropic) 또는 OpenAI를 통일된 인터페이스로 호출.

새 LLM 제공자 추가 시 이 파일만 수정하면 됨.
- _anthropic_chat(): Anthropic Claude API 호출
- _openai_chat(): OpenAI API 호출
"""

from dataclasses import dataclass
import json
from typing import Any, Optional

from config.settings import settings


@dataclass
class LLMResponse:
    """LLM 응답을 제공자 독립적으로 표현."""

    stop_reason: str  # "tool_use" | "end_turn" | "max_tokens"
    content: list[dict]  # 메시지 콘텐츠 블록 목록
    tool_uses: list[dict]  # tool_use 블록만 필터링한 목록


class LLMAdapter:
    """LLM 제공자 교체 시 이 클래스만 수정."""

    def __init__(self, provider: Optional[str] = None) -> None:
        self.provider = provider or settings.llm_provider
        self._client = self._init_client()

    def _init_client(self) -> Any:
        if self.provider == "anthropic":
            import anthropic
            return anthropic.Anthropic(api_key=settings.anthropic_api_key)
        elif self.provider == "openai":
            import openai
            return openai.OpenAI(api_key=settings.openai_api_key)
        else:
            raise ValueError(
                f"지원하지 않는 LLM 제공자: {self.provider}. "
                "'anthropic' 또는 'openai'를 사용하세요."
            )

    def chat(self, messages: list[dict], tools: list[dict], system: str) -> LLMResponse:
        """LLM에게 메시지와 도구 목록을 전달하고 응답 반환."""
        if self.provider == "anthropic":
            return self._anthropic_chat(messages, tools, system)
        elif self.provider == "openai":
            return self._openai_chat(messages, tools, system)
        else:
            raise ValueError(f"지원하지 않는 LLM 제공자: {self.provider}")

    def append_tool_results(
        self,
        messages: list[dict],
        response: LLMResponse,
        tool_results: list[dict],
    ) -> None:
        """도구 실행 결과를 제공자에 맞는 대화 이력 형식으로 추가한다."""
        if self.provider == "anthropic":
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
            return

        if self.provider == "openai":
            # OpenAI는 이전 assistant tool_calls를 다시 포함해야 후속 tool 메시지를
            # 해당 호출과 연결할 수 있다. Anthropic의 content block 형식과 호환되지 않는다.
            tool_calls = [
                {
                    "id": tool_use["id"],
                    "type": "function",
                    "function": {
                        "name": tool_use["name"],
                        "arguments": json.dumps(tool_use["input"], ensure_ascii=False),
                    },
                }
                for tool_use in response.tool_uses
            ]
            messages.append({
                "role": "assistant",
                "content": self._text_content(response.content),
                "tool_calls": tool_calls,
            })
            messages.extend({
                "role": "tool",
                "tool_call_id": result["tool_use_id"],
                "content": result["content"],
            } for result in tool_results)
            return

        raise ValueError(f"지원하지 않는 LLM 제공자: {self.provider}")

    def _anthropic_chat(
        self, messages: list[dict], tools: list[dict], system: str
    ) -> LLMResponse:
        response = self._client.messages.create(
            model=settings.anthropic_model,
            max_tokens=4096,
            system=system,
            tools=tools,
            messages=messages,
        )

        content = [block.model_dump() for block in response.content]
        tool_uses = [b for b in content if b.get("type") == "tool_use"]

        return LLMResponse(
            stop_reason=response.stop_reason,
            content=content,
            tool_uses=tool_uses,
        )

    def _openai_chat(
        self, messages: list[dict], tools: list[dict], system: str
    ) -> LLMResponse:
        # Anthropic 도구 스키마를 OpenAI 형식으로 변환
        openai_tools = [self._to_openai_tool(t) for t in tools]

        all_messages = [{"role": "system", "content": system}] + messages
        response = self._client.chat.completions.create(
            model=settings.openai_model,
            tools=openai_tools,
            messages=all_messages,
        )

        message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        content = []
        tool_uses = []

        if message.content:
            content.append({"type": "text", "text": message.content})

        if message.tool_calls:
            for tc in message.tool_calls:
                block = {
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.function.name,
                    "input": json.loads(tc.function.arguments),
                }
                content.append(block)
                tool_uses.append(block)

        # OpenAI finish_reason을 Anthropic 형식으로 통일
        stop_reason = "tool_use" if finish_reason == "tool_calls" else "end_turn"

        return LLMResponse(
            stop_reason=stop_reason,
            content=content,
            tool_uses=tool_uses,
        )

    @staticmethod
    def _text_content(content: list[dict]) -> Optional[str]:
        """표준화된 콘텐츠 블록에서 OpenAI assistant 텍스트를 추출한다."""
        texts = [block["text"] for block in content if block.get("type") == "text"]
        return "\n".join(texts) if texts else None

    @staticmethod
    def _to_openai_tool(anthropic_tool: dict) -> dict:
        """Anthropic 도구 스키마 → OpenAI 형식 변환."""
        return {
            "type": "function",
            "function": {
                "name": anthropic_tool["name"],
                "description": anthropic_tool.get("description", ""),
                "parameters": anthropic_tool.get("input_schema", {}),
            },
        }
