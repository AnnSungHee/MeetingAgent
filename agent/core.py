"""
AI Agent 핵심 루프.

Claude(또는 다른 LLM)가 도구를 호출하면 실제 도구를 실행하고,
결과를 다시 LLM에게 전달하는 사이클을 end_turn까지 반복.

AI Agent 학습 핵심 패턴:
    1. LLM에게 메시지 + 도구 목록 전달
    2. stop_reason == "tool_use" → 도구 실행
    3. tool_result를 메시지에 추가해서 LLM에게 다시 전달
    4. stop_reason == "end_turn" → 완료
"""

import json
from pathlib import Path
from typing import Optional
from uuid import uuid4

from agent.llm import LLMAdapter
from agent.prompts import build_system_prompt, build_user_message
from agent.tools import get_tools_for_outputs
from config.settings import settings
from models.session import MeetingSession, OutputResult


OUTPUT_TOOL_CHANNELS = {
    "save_markdown": "markdown",
    "create_notion_page": "notion",
    "post_to_slack": "slack",
    "post_to_kakao": "kakao",
}


class MeetingAgent:
    def __init__(self) -> None:
        settings.validate_llm()
        self.llm = LLMAdapter()

    def run(
        self,
        transcript: Optional[str] = None,
        supplementary_text: Optional[str] = None,
        output_overrides: Optional[list[str]] = None,
    ) -> MeetingSession:
        """
        회의 내용을 처리하고 결과를 반환.

        Args:
            transcript: 음성 녹취 텍스트 (Whisper STT 결과)
            supplementary_text: 추가 메모 또는 텍스트 단독 입력
            output_overrides: CLI에서 --outputs 플래그로 넘어온 채널 목록.
                              None이면 .env 설정 사용.
        """
        active_outputs = output_overrides if output_overrides is not None else settings.active_outputs()
        settings.validate_runtime(active_outputs)

        system_prompt = build_system_prompt(active_outputs)
        user_message = build_user_message(transcript, supplementary_text)
        tools = get_tools_for_outputs(active_outputs)

        messages = [{"role": "user", "content": user_message}]

        print(f"\n[Agent] 시작 - 출력 채널: {active_outputs or ['없음']}")
        print("[Agent] LLM에게 회의 내용 전달 중...\n")

        session: Optional[MeetingSession] = None
        output_results: dict[str, OutputResult] = {}
        iteration = 0

        # AI Agent 핵심 루프
        while True:
            iteration += 1
            if iteration > settings.max_agent_iterations:
                raise RuntimeError(
                    f"도구 호출이 {settings.max_agent_iterations}회를 초과했습니다. "
                    "LLM 응답을 확인하세요."
                )
            response = self.llm.chat(messages=messages, tools=tools, system=system_prompt)

            print(f"[Agent] 반복 {iteration} - stop_reason: {response.stop_reason}")

            if response.stop_reason == "end_turn" or not response.tool_uses:
                print("[Agent] 완료.\n")
                break

            # tool_use 블록 실행
            tool_results = []
            for tool_use in response.tool_uses:
                tool_name = tool_use["name"]
                tool_input = tool_use["input"]
                tool_use_id = tool_use["id"]

                channel = OUTPUT_TOOL_CHANNELS.get(tool_name)
                if channel and session is None:
                    result = {
                        "success": False,
                        "error": "save_session_summary가 성공하기 전에 출력 도구를 실행할 수 없습니다.",
                    }
                else:
                    print(f"[Agent] 도구 실행: {tool_name}")
                    result = self._execute_tool(tool_name, tool_input)

                # save_session_summary 결과로 MeetingSession 생성
                if tool_name == "save_session_summary" and result.get("success"):
                    session = result["session"]

                if channel:
                    # 한 채널의 일시적 장애가 다른 채널 배포를 막지 않도록 결과만 기록한다.
                    output_results[channel] = OutputResult(
                        channel=channel,
                        success=result.get("success", False),
                        error=result.get("error"),
                    )

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": json.dumps(
                        {k: v for k, v in result.items() if k != "session"},
                        ensure_ascii=False,
                    ),
                    "is_error": not result.get("success", True),
                })

            # 제공자별 메시지 형식 변환은 LLMAdapter가 담당한다.
            self.llm.append_tool_results(messages, response, tool_results)

        if session is None:
            raise RuntimeError(
                "save_session_summary 도구가 호출되지 않았습니다. "
                "시스템 프롬프트 또는 도구 스키마를 확인하세요."
            )

        missing_outputs = set(active_outputs) - set(output_results)
        # 프롬프트 지시만으로는 출력 도구 호출을 보장할 수 없으므로 종료 시 강제 검증한다.
        if missing_outputs:
            raise RuntimeError(
                "활성화된 출력 도구가 호출되지 않았습니다: "
                f"{', '.join(sorted(missing_outputs))}"
            )

        session.output_results = list(output_results.values())
        self._persist_session(session, transcript, supplementary_text)
        return session

    def _execute_tool(self, tool_name: str, tool_input: dict) -> dict:
        """도구 이름에 맞는 함수를 실행하고 결과 반환."""
        try:
            if tool_name == "save_session_summary":
                return self._save_session_summary(tool_input)
            elif tool_name == "save_markdown":
                from outputs.markdown import save_markdown
                return save_markdown(**tool_input)
            elif tool_name == "create_notion_page":
                from outputs.notion import create_notion_page
                return create_notion_page(**tool_input)
            elif tool_name == "post_to_slack":
                from outputs.slack import post_to_slack
                return post_to_slack(**tool_input)
            elif tool_name == "post_to_kakao":
                from outputs.kakao import post_to_kakao
                return post_to_kakao(**tool_input)
            else:
                return {"success": False, "error": f"알 수 없는 도구: {tool_name}"}
        except Exception as e:
            print(f"[Agent] 도구 실행 오류 ({tool_name}): {e}")
            return {"success": False, "error": str(e)}

    def _save_session_summary(self, tool_input: dict) -> dict:
        """회의 요약 데이터를 Pydantic 모델로 변환 후 저장."""
        from datetime import datetime

        date_str = datetime.now().strftime("%Y-%m-%d")
        session_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{uuid4().hex[:8]}"

        session = MeetingSession(
            session_id=session_id,
            date=date_str,
            **tool_input,
        )

        return {"success": True, "session": session, "session_id": session_id}

    def _persist_session(
        self,
        session: MeetingSession,
        transcript: Optional[str],
        supplementary_text: Optional[str],
    ) -> None:
        """처리된 세션을 JSON 파일로 저장."""
        session.raw_transcript = transcript or supplementary_text

        data_dir = Path(settings.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)

        output_path = data_dir / f"{session.session_id}.json"
        output_path.write_text(
            session.model_dump_json(indent=2),
            encoding="utf-8",
        )
        print(f"[Agent] 세션 저장 완료: {output_path}")
