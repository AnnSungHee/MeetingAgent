"""
LLM 어댑터: Claude, OpenAI 또는 Codex를 통일된 인터페이스로 호출.

새 LLM 제공자 추가 시 이 파일만 수정하면 됨.
- _anthropic_chat(): Anthropic Claude API 호출
- _openai_chat(): OpenAI API 호출
- _codex_chat(): 로그인된 Codex CLI 단일 호출
"""

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Optional
from uuid import uuid4

from config.settings import settings
from agent.renderers import build_output_tool_inputs
from models.usage import UsageStore


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
        self.requires_tool_result_roundtrip = self.provider != "codex"
        self._client = self._init_client()

    def _init_client(self) -> Any:
        if self.provider == "anthropic":
            import anthropic
            return anthropic.Anthropic(api_key=settings.anthropic_api_key)
        elif self.provider == "openai":
            import openai
            return openai.OpenAI(api_key=settings.openai_api_key)
        elif self.provider == "codex":
            return None
        else:
            raise ValueError(
                f"지원하지 않는 LLM 제공자: {self.provider}. "
                "'anthropic', 'openai', 'codex' 중 하나를 사용하세요."
            )

    def chat(self, messages: list[dict], tools: list[dict], system: str) -> LLMResponse:
        """LLM에게 메시지와 도구 목록을 전달하고 응답 반환."""
        if self.provider == "anthropic":
            return self._anthropic_chat(messages, tools, system)
        elif self.provider == "openai":
            return self._openai_chat(messages, tools, system)
        elif self.provider == "codex":
            return self._codex_chat(messages, tools, system)
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

        if self.provider == "codex":
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
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

    def _codex_chat(
        self, messages: list[dict], tools: list[dict], system: str
    ) -> LLMResponse:
        """Codex CLI 한 번으로 모든 활성 출력 도구의 입력을 생성한다."""
        summary_tool = next(
            tool for tool in tools if tool["name"] == "save_session_summary"
        )
        # 채널별 문구는 구조화 요약에서 로컬 생성해 중복 출력 토큰을 없앤다.
        output_schema = self._codex_output_schema([summary_tool])
        prompt = self._codex_prompt(messages)
        usage_store = UsageStore(
            settings.token_usage_path, settings.codex_token_budget
        )
        run_id = usage_store.start_run()
        usage: dict = {}

        try:
            with tempfile.TemporaryDirectory(prefix="meeting-agent-codex-") as temp_dir:
                schema_path = Path(temp_dir) / "response-schema.json"
                schema_path.write_text(
                    json.dumps(output_schema, ensure_ascii=False), encoding="utf-8"
                )
                command = [
                    settings.codex_command,
                    "exec",
                    "--json",
                    "--ephemeral",
                    "--ignore-user-config",
                    "--skip-git-repo-check",
                    "--sandbox",
                    "read-only",
                    "--config",
                    f'model_reasoning_effort="{settings.codex_reasoning_effort}"',
                    "--config",
                    'model_reasoning_summary="none"',
                    "--config",
                    'model_verbosity="low"',
                    "--output-schema",
                    str(schema_path),
                ]
                if settings.codex_model:
                    command.extend(["--model", settings.codex_model])
                command.append("-")

                completed = subprocess.run(
                    command,
                    input=prompt,
                    text=True,
                    capture_output=True,
                    cwd=temp_dir,
                    timeout=settings.codex_timeout_seconds,
                    check=False,
                )

            final_text, usage, event_error = self._parse_codex_events(completed.stdout)
            if completed.returncode != 0 or event_error:
                detail = event_error or completed.stderr.strip() or "알 수 없는 오류"
                raise RuntimeError(f"Codex 실행 실패: {detail[-2000:]}")
            if not final_text:
                raise RuntimeError("Codex가 최종 구조화 응답을 반환하지 않았습니다.")

            payload = json.loads(final_text)
            summary = self._drop_nulls(payload["save_session_summary"])
            tool_inputs = build_output_tool_inputs(
                summary, [tool["name"] for tool in tools]
            )
            tool_uses = []
            for tool in tools:
                name = tool["name"]
                tool_uses.append({
                    "type": "tool_use",
                    "id": f"codex-{uuid4().hex}",
                    "name": name,
                    "input": tool_inputs[name],
                })
            usage_store.finish_run(run_id, usage)
            return LLMResponse(
                stop_reason="tool_use",
                content=tool_uses,
                tool_uses=tool_uses,
            )
        except Exception as exc:
            usage_store.fail_run(run_id, str(exc), usage)
            raise

    @staticmethod
    def _codex_prompt(messages: list[dict]) -> str:
        conversation = []
        for message in messages:
            content = message.get("content", "")
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False)
            conversation.append(f"[{message.get('role', 'user')}]\n{content}")
        return (
            "프로그래밍 스터디 회의 기록자 역할입니다. 아래 회의 내용에서 참석자, "
            "논의 주제와 결정, 담당자별 액션 아이템, 다음 주 계획을 정확히 추출하세요. "
            "없는 액션 아이템은 만들지 말고 기술 용어는 원문을 유지하세요. "
            "파일이나 명령은 사용하지 말고 최종 응답은 JSON Schema를 따르세요.\n\n"
            + "\n\n".join(conversation)
        )

    @classmethod
    def _codex_output_schema(cls, tools: list[dict]) -> dict:
        properties = {
            tool["name"]: cls._strict_schema(tool["input_schema"])
            for tool in tools
        }
        return {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }

    @classmethod
    def _strict_schema(cls, schema: dict) -> dict:
        """설명을 제거하고 Structured Outputs용 strict schema로 변환한다."""
        schema = {key: value for key, value in schema.items() if key != "description"}
        if schema.get("type") == "object":
            original_required = set(schema.get("required", []))
            properties = {}
            for name, child in schema.get("properties", {}).items():
                strict_child = cls._strict_schema(child)
                if name not in original_required:
                    strict_child = {"anyOf": [strict_child, {"type": "null"}]}
                properties[name] = strict_child
            schema["properties"] = properties
            schema["required"] = list(properties)
            schema["additionalProperties"] = False
        elif schema.get("type") == "array" and "items" in schema:
            schema["items"] = cls._strict_schema(schema["items"])
        return schema

    @staticmethod
    def _drop_nulls(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: LLMAdapter._drop_nulls(child)
                for key, child in value.items()
                if child is not None
            }
        if isinstance(value, list):
            return [LLMAdapter._drop_nulls(child) for child in value]
        return value

    @staticmethod
    def _parse_codex_events(stdout: str) -> tuple[Optional[str], dict, Optional[str]]:
        final_text: Optional[str] = None
        usage: dict = {}
        error: Optional[str] = None
        for line in stdout.splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            event_type = event.get("type")
            item = event.get("item", {})
            if (
                event_type == "item.completed"
                and item.get("type") == "agent_message"
            ):
                final_text = item.get("text")
            elif event_type == "turn.completed":
                usage = event.get("usage", {})
            elif event_type in {"turn.failed", "error"}:
                error = str(event.get("error") or event.get("message") or event)
        return final_text, usage, error

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
