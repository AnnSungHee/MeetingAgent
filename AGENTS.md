# AGENTS.md — AI Agent 설계 문서

MeetingAgent의 AI Agent 구조, 도구 설계 원칙, 확장 방법을 설명한다.

---

## Agent 구조 개요

이 프로젝트는 **단일 Agent + 다중 도구(Tool Use)** 패턴을 사용한다.

```
MeetingAgent
    │
    ├── 역할: 프로그래밍 스터디 회의 기록 전문가
    ├── LLM: Codex CLI (기본) / Claude / OpenAI
    └── 도구 목록:
        ├── save_session_summary   (필수 - 항상 호출)
        ├── save_markdown          (OUTPUT_MARKDOWN=true 시)
        ├── create_notion_page     (OUTPUT_NOTION=true 시)
        ├── post_to_slack          (OUTPUT_SLACK=true 시)
        └── post_to_kakao          (OUTPUT_KAKAO=true 시)
```

---

## Agent 루프 원리

```
1. 사용자 입력 (transcript) → LLM에게 전달
2. LLM이 tool_use 블록 반환
3. 코드가 해당 도구 실행
4. API provider는 tool_result를 LLM에게 반환하고 end_turn까지 반복
5. Codex provider는 모든 입력을 단일 호출로 생성하고 추가 왕복을 생략
```

코드 위치: [agent/core.py](agent/core.py)

**핵심**: LLM이 구조화된 회의 요약을 만들고, 코드가 채널별 내용을 렌더링하고 실제 출력한다.
Codex provider에서는 중복 출력 토큰을 줄이기 위해 Markdown/Slack/Notion/Kakao
payload를 회의 요약 JSON에서 로컬 생성한다.

---

## 시스템 프롬프트 설계 원칙

파일: [agent/prompts.py](agent/prompts.py)

### 역할 정의

```
당신은 프로그래밍 스터디 그룹의 전문 회의 기록자입니다.
회의 내용을 분석해 참석자, 주요 논의 사항, 결정 사항, 
액션 아이템, 다음 주 계획을 구조적으로 추출하세요.
```

### 도구 호출 지침

시스템 프롬프트에 활성화된 출력 채널 목록을 명시해서 Claude가 어떤 도구를 호출해야 하는지 알게 한다:

```
활성화된 출력 채널: markdown, slack
다음 도구를 모두 호출하세요: save_session_summary, save_markdown, post_to_slack
```

### 유저 메시지 구조

```
[회의 녹취록]
{whisper_transcript}

[추가 메모 및 코멘트]        ← 텍스트 보조 입력이 있을 때만 포함
{supplementary_text}
```

---

## 도구(Tool) 설계 원칙

파일: [agent/tools.py](agent/tools.py)

### 1. `description`은 Claude를 위한 설명이다

Claude가 이 도구를 언제, 왜 호출해야 하는지 명확히 서술한다.

```python
"description": (
    "회의 전체를 구조화된 형태로 추출합니다. "
    "이 도구는 항상 첫 번째로 호출되어야 하며, "
    "모든 참석자, 논의 사항, 액션 아이템을 빠짐없이 포함하세요."
)
```

### 2. `input_schema`는 Pydantic 모델과 일치시킨다

`models/session.py`의 Pydantic 모델과 도구 스키마를 동기화 유지.
한쪽을 수정하면 반드시 다른 쪽도 수정.

### 3. 모든 필드에 `description` 작성

Claude가 각 필드에 어떤 데이터를 넣어야 하는지 명확히:

```python
"member": {
    "type": "string",
    "description": "액션 아이템 담당자 이름 (회의에서 언급된 실명)"
}
```

---

## 도구 목록 상세

### `save_session_summary`

**역할**: 회의 전체를 구조화된 JSON으로 추출. 항상 첫 번째로 호출.

**반환값**: `MeetingSession` 형식의 딕셔너리 → `data/sessions/{date}.json`에 저장

**주의**: 이 도구가 실패하면 전체 파이프라인을 중단한다 (나머지 도구의 기반 데이터).

---

### `save_markdown`

**역할**: 처리된 회의 내용을 마크다운 파일로 저장.

**조건**: `OUTPUT_MARKDOWN=true`일 때만 도구 목록에 포함.

**출력 파일**: `data/sessions/YYYY-MM-DD.md`

---

### `create_notion_page`

**역할**: Notion 데이터베이스에 회의 요약 페이지 생성.

**조건**: `OUTPUT_NOTION=true`이고 `NOTION_API_KEY`, `NOTION_DATABASE_ID` 설정 시.

**실패 처리**: Notion API 오류 시 `is_error: true` 반환, 나머지 도구는 계속 실행.

---

### `post_to_slack`

**역할**: Slack 채널에 회의 요약 메시지 발송.

**조건**: `OUTPUT_SLACK=true`이고 `SLACK_BOT_TOKEN`, `SLACK_CHANNEL` 설정 시.

---

### `post_to_kakao`

**역할**: KakaoTalk으로 회의 요약 메시지 발송.

**조건**: `OUTPUT_KAKAO=true`이고 `KAKAO_WEBHOOK_URL` 설정 시.

---

## 새 도구 추가 방법

### 1단계: 출력 모듈 작성

```python
# outputs/github.py

def post_to_github(title: str, content: str) -> dict:
    """GitHub Issue로 회의 내용 등록"""
    try:
        # ... GitHub API 호출
        return {"success": True, "url": issue_url}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

### 2단계: 도구 스키마 추가

```python
# agent/tools.py에 추가

POST_TO_GITHUB_TOOL = {
    "name": "post_to_github",
    "description": "GitHub Issue를 생성해 회의 내용을 등록합니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Issue 제목"},
            "content": {"type": "string", "description": "Issue 본문 (마크다운)"}
        },
        "required": ["title", "content"]
    }
}
```

### 3단계: core.py 도구 라우터에 등록

```python
# agent/core.py의 _execute_tool() 메서드에 추가

elif tool_name == "post_to_github":
    from outputs.github import post_to_github
    result = post_to_github(**tool_input)
```

### 4단계: settings.py에 환경 변수 추가

```python
# config/settings.py
output_github: bool = Field(default=False, alias="OUTPUT_GITHUB")
github_token: Optional[str] = Field(default=None, alias="GITHUB_TOKEN")
github_repo: Optional[str] = Field(default=None, alias="GITHUB_REPO")
```

### 5단계: .env.example 업데이트

```
OUTPUT_GITHUB=false
GITHUB_TOKEN=ghp_...
GITHUB_REPO=username/study-notes
```

---

## LLM 어댑터 확장

새 LLM 제공자 추가 시 `agent/llm.py`를 중심으로 수정:

```python
# agent/llm.py

elif self.provider == "gemini":
    return self._gemini_chat(messages, tools)

def _gemini_chat(self, messages, tools) -> LLMResponse:
    # Google Gemini API 호출 구현
    ...
```

도구 스키마 변환(Anthropic ↔ OpenAI 형식)도 `llm.py` 내부에서 처리.

---

## 프롬프트 개선 시 주의사항

1. 시스템 프롬프트 변경 후 반드시 실제 스터디 텍스트로 테스트
2. Claude가 `save_session_summary`를 빠뜨리는 경우 → 시스템 프롬프트의 도구 호출 지침 강화
3. 액션 아이템에서 담당자를 추출 못하는 경우 → `member` 필드 description 수정
4. 다음 주 계획이 너무 빈약한 경우 → `next_week_plan` 도구 스키마의 description 보강
