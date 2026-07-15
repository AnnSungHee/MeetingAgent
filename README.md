# MeetingAgent

프로그래밍 스터디 그룹(4~6명)을 위한 AI Agent 기반 회의 자동 기록 시스템.

스터디가 끝나면 음성 녹음 또는 텍스트를 입력하면, AI가 자동으로:
- 회의 내용 요약
- 참석자별 액션 아이템 추출
- 다음 주 스터디 계획 작성
- Notion, Slack, KakaoTalk, Markdown 등 원하는 채널에 배포

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| 음성 → 텍스트 | OpenAI Whisper로 녹음 파일을 자동 변환 |
| 회의 요약 | Claude AI가 핵심 내용을 구조화 |
| 액션 아이템 | 참석자별 할 일과 기한 자동 추출 |
| 다음 주 계획 | 다음 스터디 주제 및 준비 사항 제안 |
| 멀티 채널 배포 | Notion / Slack / KakaoTalk / Markdown |

---

## 아키텍처

```
입력 (음성 또는 텍스트)
    │
    ├── 음성 파일 → Whisper STT → transcript
    └── 텍스트 직접 입력 → transcript
                │
                ▼
    ┌─────────────────────────────────────┐
    │   AGENT LOOP (agent/core.py)        │
    │   LLM API + Tool Use                │
    │   tool_use → execute → tool_result  │
    │   → loop until end_turn             │
    └─────────────────────────────────────┘
                │
    ┌───────────┼──────────────────────┐
    ▼           ▼            ▼         ▼
Notion      Slack       KakaoTalk  Markdown
```

---

## 설치

### 요구사항

- Python 3.10 이상
- ffmpeg (Whisper 음성 인식에 필요)

### 의존성 설치

```bash
uv venv
uv pip install -r requirements.txt
```

### 환경 변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 API 키 입력
```

최소 설정 (Phase 1 로컬 동작):
```
ANTHROPIC_API_KEY=sk-ant-...
OUTPUT_MARKDOWN=true
```

---

## 사용법

### 텍스트 입력 (녹음 없이)

```bash
python main.py --text "오늘 스터디에서 FastAPI 기초를 다뤘다. 홍길동이 발표했고..."
```

### 음성 파일 입력

```bash
python main.py --audio meeting.mp3
```

### 음성 + 추가 메모

```bash
python main.py --audio meeting.mp3 --text "추가 메모: 다음 주 발표자는 김철수"
```

### 출력 채널 선택

```bash
python main.py --audio meeting.mp3 --outputs markdown,notion,slack
```

---

## 프로젝트 구조

```
MeetingAgent/
├── main.py                 # CLI 진입점
├── agent/
│   ├── core.py             # AI Agent 루프 (핵심)
│   ├── llm.py              # LLM 어댑터 (Claude/OpenAI 전환 가능)
│   ├── prompts.py          # 프롬프트 템플릿
│   └── tools.py            # 도구 스키마 정의
├── inputs/
│   ├── audio.py            # Whisper STT
│   └── text.py             # 텍스트 입력 처리
├── outputs/
│   ├── notion.py           # Notion API
│   ├── slack.py            # Slack 웹훅
│   ├── kakao.py            # KakaoTalk
│   └── markdown.py         # 마크다운 파일 저장
├── models/
│   └── session.py          # Pydantic 데이터 모델
├── config/
│   └── settings.py         # 환경 변수 로딩
├── data/sessions/          # 처리된 세션 JSON 저장소
```

---

## 개발 단계

- **Phase 0** ✅ 문서화 (README, CLAUDE.md, AGENTS.md)
- **Phase 1** 로컬 동작 핵심 (텍스트/음성 입력 → Markdown 출력)
- **Phase 2** 외부 연동 (Notion / Slack / KakaoTalk)
- **Phase 3** 웹 대시보드 (예정)

---

## LLM 교체

기본값은 Claude (Anthropic)이지만 `.env`에서 교체 가능:

```
LLM_PROVIDER=openai   # anthropic (기본) 또는 openai
OPENAI_API_KEY=sk-...
```

`agent/llm.py` 하나만 수정하면 새 LLM 제공자를 추가할 수 있습니다.

## 테스트

외부 API 키나 음성 파일 없이 핵심 도구 루프를 검증합니다.

```bash
uv run pytest
```

---

## 기여

이 프로젝트는 AI Agent 학습을 위한 실습 프로젝트입니다.
[AGENTS.md](AGENTS.md)를 먼저 읽고 도구 추가 방법을 확인하세요.
