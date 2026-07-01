"""
Claude에게 전달할 시스템 프롬프트와 유저 메시지 템플릿.
"""

from typing import Optional


SYSTEM_PROMPT_TEMPLATE = """\
당신은 프로그래밍 스터디 그룹의 전문 회의 기록자입니다.

## 역할
회의 내용(녹취록 또는 메모)을 분석해 다음 내용을 정확하게 추출합니다:
- 참석자 명단
- 논의된 주요 주제와 결정 사항
- 참석자별 액션 아이템 (담당자와 할 일이 명확해야 함)
- 다음 주 스터디 계획

## 스터디 맥락
- 4~6명의 프로그래밍 스터디 그룹
- 매주 정기적으로 모여 특정 기술 또는 주제를 공부
- 발표자가 돌아가며 진행하고, 질문과 토론이 활발히 이루어짐

## 도구 호출 지침
다음 순서로 도구를 호출하세요:
1. **save_session_summary** — 항상 첫 번째로 호출. 회의 전체 내용을 구조화.
{output_instructions}

## 주의사항
- 이름이 명확하지 않은 경우 "참석자1", "참석자2" 등으로 표기
- 추측이 필요한 경우 자연스럽게 추론하되, 확실하지 않은 내용은 "~로 보임" 표현 사용
- 기술 용어는 영어 원문 유지 (예: FastAPI, GitHub Actions, Docker)
- 액션 아이템이 없는 경우 빈 배열 반환 (억지로 만들지 말 것)
"""


def build_system_prompt(active_outputs: list[str]) -> str:
    """활성화된 출력 채널을 포함한 시스템 프롬프트 생성."""
    if not active_outputs:
        output_instructions = "2. 출력 채널이 없습니다. save_session_summary만 호출하세요."
    else:
        tool_names = ["save_session_summary"] + [
            _output_to_tool_name(o) for o in active_outputs
        ]
        tools_str = ", ".join(tool_names)
        channels_str = ", ".join(active_outputs)
        output_instructions = (
            f"2. 그 다음 활성화된 채널({channels_str})에 맞는 도구를 순서대로 호출하세요.\n"
            f"   호출해야 할 도구: {tools_str}"
        )

    return SYSTEM_PROMPT_TEMPLATE.format(output_instructions=output_instructions)


def build_user_message(
    transcript: Optional[str],
    supplementary_text: Optional[str],
) -> str:
    """
    회의 내용과 추가 메모를 합쳐 유저 메시지 생성.

    - transcript만 있으면: 녹취록 단독 사용
    - supplementary_text만 있으면: 텍스트를 회의 내용으로 처리
    - 둘 다 있으면: 녹취록 + 추가 메모 구분해서 전달
    """
    parts = []

    if transcript and supplementary_text:
        parts.append("[회의 녹취록]")
        parts.append(transcript.strip())
        parts.append("")
        parts.append("[추가 메모 및 코멘트]")
        parts.append(supplementary_text.strip())
    elif transcript:
        parts.append("[회의 녹취록]")
        parts.append(transcript.strip())
    elif supplementary_text:
        parts.append("[회의 내용]")
        parts.append(supplementary_text.strip())
    else:
        raise ValueError("transcript 또는 supplementary_text 중 하나는 반드시 있어야 합니다.")

    parts.append("")
    parts.append("위 내용을 바탕으로 회의 기록을 작성해주세요.")

    return "\n".join(parts)


def _output_to_tool_name(output: str) -> str:
    mapping = {
        "markdown": "save_markdown",
        "notion": "create_notion_page",
        "slack": "post_to_slack",
        "kakao": "post_to_kakao",
    }
    return mapping.get(output, output)
