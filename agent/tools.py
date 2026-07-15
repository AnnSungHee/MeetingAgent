"""
Claude에게 제공할 도구(Tool) 스키마 정의.

각 도구의 input_schema는 models/session.py의 Pydantic 모델과 동기화 유지.
새 도구 추가 방법은 AGENTS.md 참고.
"""

SAVE_SESSION_SUMMARY_TOOL = {
    "name": "save_session_summary",
    "description": (
        "스터디 회의 전체 내용을 구조화된 형태로 추출합니다. "
        "이 도구는 항상 가장 먼저 호출되어야 합니다. "
        "회의에서 언급된 모든 참석자, 논의 주제, 결정 사항, 액션 아이템을 "
        "빠짐없이 포함하세요. 언급이 불분명한 경우 최선을 다해 추론하세요."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "participants": {
                "type": "array",
                "items": {"type": "string"},
                "description": "이번 스터디에 참석한 사람들의 이름 목록",
            },
            "overall_summary": {
                "type": "string",
                "description": "오늘 스터디 전체 내용을 2~3문단으로 요약. 주요 학습 내용과 분위기 포함.",
            },
            "topics_discussed": {
                "type": "array",
                "description": "논의된 주제 목록. 각 주제별 요약과 결정 사항 포함.",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "주제 제목 (예: 'FastAPI 라우터 구조 이해')",
                        },
                        "summary": {
                            "type": "string",
                            "description": "해당 주제에서 논의한 내용 요약",
                        },
                        "decisions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "이 주제에서 내린 결정 사항들",
                        },
                    },
                    "required": ["title", "summary"],
                },
            },
            "action_items": {
                "type": "array",
                "description": "참석자별 할 일 목록. 담당자가 명시된 모든 과제를 포함.",
                "items": {
                    "type": "object",
                    "properties": {
                        "member": {
                            "type": "string",
                            "description": "담당자 이름 (회의에서 언급된 실명)",
                        },
                        "task": {
                            "type": "string",
                            "description": "해야 할 일의 구체적인 내용",
                        },
                        "deadline": {
                            "type": "string",
                            "description": "기한 (예: '다음 주 스터디 전까지', '2026-07-01'). 언급 없으면 null.",
                        },
                    },
                    "required": ["member", "task"],
                },
            },
            "next_week_plan": {
                "type": "object",
                "description": "다음 주 스터디 계획",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "다음 스터디 예정 날짜 또는 요일 (언급된 경우만)",
                    },
                    "topics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "다음 주에 다룰 주제 목록",
                    },
                    "preparation": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "다음 스터디 전에 준비해야 할 사항",
                    },
                    "presenter": {
                        "type": "string",
                        "description": "다음 주 발표자 이름 (언급된 경우만)",
                    },
                },
                "required": ["topics"],
            },
        },
        "required": [
            "participants",
            "overall_summary",
            "topics_discussed",
            "action_items",
            "next_week_plan",
        ],
    },
}

SAVE_MARKDOWN_TOOL = {
    "name": "save_markdown",
    "description": (
        "정리된 회의 내용을 마크다운 형식으로 저장합니다. "
        "save_session_summary 호출 후에 사용하세요. "
        "마크다운은 사람이 읽기 좋게 작성하고, 섹션 구분을 명확히 하세요."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "저장할 파일명 (예: '2026-06-22-study.md'). 날짜 포함 권장.",
            },
            "content": {
                "type": "string",
                "description": (
                    "마크다운 파일 전체 내용. "
                    "## 참석자, ## 주요 내용, ## 액션 아이템, ## 다음 주 계획 섹션 포함."
                ),
            },
        },
        "required": ["filename", "content"],
    },
}

CREATE_NOTION_PAGE_TOOL = {
    "name": "create_notion_page",
    "description": (
        "Notion 데이터베이스에 회의 요약 페이지를 생성합니다. "
        "save_session_summary 호출 후에 사용하세요."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Notion 페이지 제목 (예: '2026-06-22 스터디 회의록')",
            },
            "content": {
                "type": "string",
                "description": "Notion 페이지 본문 내용 (마크다운 형식)",
            },
        },
        "required": ["title", "content"],
    },
}

POST_TO_SLACK_TOOL = {
    "name": "post_to_slack",
    "description": (
        "Slack 채널에 회의 요약 메시지를 발송합니다. "
        "핵심 내용만 간결하게 작성하세요 (Slack 메시지는 너무 길면 안 읽힘)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": (
                    "Slack에 보낼 메시지. "
                    "오늘 스터디 요약, 주요 결정 사항, 다음 주 주제를 간결하게 정리. "
                    "이모지와 볼드체(*텍스트*)로 가독성 높이기."
                ),
            },
        },
        "required": ["message"],
    },
}

POST_TO_KAKAO_TOOL = {
    "name": "post_to_kakao",
    "description": (
        "KakaoTalk으로 회의 요약 메시지를 발송합니다. "
        "카카오는 마크다운을 지원하지 않으므로 일반 텍스트로 작성하세요."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": (
                    "카카오톡에 보낼 메시지 (순수 텍스트). "
                    "오늘 스터디 요약과 다음 주 계획을 간결하게 정리."
                ),
            },
        },
        "required": ["message"],
    },
}


def get_tools_for_outputs(active_outputs: list[str]) -> list[dict]:
    """활성화된 출력 채널에 맞는 도구 목록 반환."""
    tools = [SAVE_SESSION_SUMMARY_TOOL]

    output_tool_map = {
        "markdown": SAVE_MARKDOWN_TOOL,
        "notion": CREATE_NOTION_PAGE_TOOL,
        "slack": POST_TO_SLACK_TOOL,
        "kakao": POST_TO_KAKAO_TOOL,
    }

    for output in active_outputs:
        if output in output_tool_map:
            tools.append(output_tool_map[output])

    return tools
