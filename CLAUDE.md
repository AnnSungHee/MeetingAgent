# CLAUDE.md — MeetingAgent 프로젝트 규칙

Claude Code가 이 프로젝트에서 작업할 때 반드시 따르는 규칙.

---

## 프로젝트 개요

AI Agent 기반 스터디 회의 자동 기록 시스템. AI Agent 학습과 바이브 코딩 실습을 겸하는 프로젝트로, 코드의 가독성과 학습 친화성이 중요하다.

---

## 코드 스타일

- Python 3.10+ 문법 사용
- 타입 힌트 필수 (`def foo(x: str) -> dict:`)
- Pydantic 모델로 데이터 유효성 검증
- 함수 하나는 하나의 역할만 담당
- 주석은 WHY가 명확하지 않을 때만 작성 (WHAT 설명 금지)
- 파일당 300줄 이하 유지

## 임포트 순서

```python
# 1. 표준 라이브러리
import os
from pathlib import Path

# 2. 서드파티
import anthropic
from pydantic import BaseModel

# 3. 로컬
from config.settings import settings
from models.session import MeetingSession
```

---

## 핵심 아키텍처 규칙

### LLM 호출은 반드시 `agent/llm.py`를 통해서만

`agent/core.py`나 다른 파일에서 `anthropic.Anthropic()`를 직접 호출하지 말 것.
LLM 제공자 교체 시 `llm.py` 하나만 수정하면 되도록 유지한다.

### 도구 실행은 `agent/core.py`에서만

출력 모듈(`outputs/`)을 직접 호출하는 코드가 `core.py` 외부에 있으면 안 됨.

### 출력 모듈은 독립적으로 동작

각 `outputs/*.py`는 다른 출력 모듈에 의존하지 않는다. 하나가 실패해도 나머지는 계속 실행.

### 설정은 반드시 `config/settings.py`에서

환경 변수를 `os.environ.get()`으로 직접 읽지 말 것. `from config.settings import settings`를 사용.

---

## 디렉토리 구조 규칙

새 파일 추가 시:
- LLM 관련 → `agent/`
- 입력 처리 → `inputs/`
- 출력 채널 → `outputs/`
- 데이터 모델 → `models/`
- 웹 UI → `web/`

`data/sessions/`에는 코드를 두지 말 것 (JSON 데이터만 저장).

---

## 오류 처리 규칙

- 외부 API 호출(Notion, Slack, KakaoTalk)은 try/except로 감싸고 실패 시 `is_error: true`를 tool_result로 반환
- Whisper STT 실패 시 사용자에게 명확한 오류 메시지 출력
- API 키 누락 시 `config/settings.py`에서 ValueError를 즉시 raise (묵시적 실패 금지)

```python
# 올바른 오류 처리 예시
def post_to_slack(message: str) -> dict:
    try:
        # ... slack API 호출
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

---

## 테스트 방법

```bash
# Phase 1 빠른 테스트 (텍스트 입력)
python main.py --text "테스트 스터디 내용입니다. 참석자: 홍길동, 김철수. FastAPI를 공부했습니다."

# Phase 1 음성 테스트
python main.py --audio tests/sample.mp3

# 특정 출력만 활성화
python main.py --text "..." --outputs markdown

# 대시보드 실행 (Phase 3)
streamlit run web/app.py
```

---

## 환경 변수

`.env.example`을 복사해서 `.env`를 만든다. `.env`는 절대 커밋하지 말 것.

최소 실행 환경:
```
ANTHROPIC_API_KEY=...
OUTPUT_MARKDOWN=true
```

---

## 금지 사항

- `.env` 파일 커밋 금지
- `data/sessions/` 내 JSON 파일 커밋 금지 (개인 스터디 기록 포함 가능)
- `agent/llm.py` 우회해서 LLM 직접 호출 금지
- `print()`로 디버깅 코드 남기는 것 금지 (사용 후 제거)
