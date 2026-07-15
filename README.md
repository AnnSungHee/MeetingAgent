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
| 회의 요약 | Claude/OpenAI/Codex가 핵심 내용을 구조화 |
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
    │   LLM API 또는 Codex CLI + Tool Use │
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
- 로그인된 Codex CLI (기본 LLM provider 사용 시)

### 의존성 설치

```bash
uv venv
uv pip install -r requirements.txt
codex login
```

### 환경 변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 실행 방식 설정
```

최소 설정 (Phase 1 로컬 동작):
```
LLM_PROVIDER=codex
CODEX_TOKEN_BUDGET=1000000
OUTPUT_MARKDOWN=true
```

`LLM_PROVIDER`를 생략해도 기본값은 `codex`입니다.

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

Claude/OpenAI API 외에 로그인된 Codex CLI를 사용할 수 있습니다:

```
LLM_PROVIDER=codex
CODEX_TOKEN_BUDGET=1000000  # 웹 화면에서 사용할 로컬 관리 예산
CODEX_REASONING_EFFORT=low
```

Codex 경로는 회의 요약 JSON을 한 번만 생성하고 채널별 문구는 로컬에서 렌더링하며,
도구 결과 확인을 위한 추가 모델 왕복도 생략해 토큰 사용을 줄입니다. Codex CLI의
저장된 로그인 인증을 재사용하므로 프로젝트에 LLM API Key를 저장하지 않습니다.
추론 effort와 응답 verbosity도 낮게 고정합니다. 다만 `codex exec` 자체 에이전트
지침에 따른 입력 토큰 베이스라인은 존재합니다.

### 토큰 사용량 대시보드

```bash
python dashboard.py --port 8501
```

브라우저에서 `http://127.0.0.1:8501`을 열면 최근 호출, 누적 토큰,
캐시/추론 토큰, 실제 Codex 계정의 5시간·주간 한도와 초기화 시각을 확인할 수
있습니다. 실제 계정 값은 Codex App Server의 `account/rateLimits/read`와
`account/usage/read`에서 가져오며 30초간 캐시합니다. App Server 연결 실패 시에도
`CODEX_TOKEN_BUDGET` 기준의 로컬 잔여량은 계속 표시됩니다.

## 테스트

외부 API 키나 음성 파일 없이 핵심 도구 루프를 검증합니다.

```bash
uv run pytest
```

---

## 기여

이 프로젝트는 AI Agent 학습을 위한 실습 프로젝트입니다.
[AGENTS.md](AGENTS.md)를 먼저 읽고 도구 추가 방법을 확인하세요.
