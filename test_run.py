"""테스트 실행 스크립트 - 결과를 파일로 저장."""
import sys
import os

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

LOG_FILE = "test_result.log"

def log(msg: str) -> None:
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

# 로그 초기화
with open(LOG_FILE, "w", encoding="utf-8") as f:
    f.write("")

try:
    from agent.core import MeetingAgent

    text_path = "음성 009_음성 메모_memo.txt"
    with open(text_path, encoding="utf-8") as f:
        content = f.read()

    log(f"[테스트] 파일 로드 완료: {len(content)}자")
    log("[테스트] Agent 실행 시작...\n")

    agent = MeetingAgent()
    session = agent.run(supplementary_text=content)

    log("\n" + "=" * 60)
    log(f"날짜: {session.date}")
    log(f"참석자: {', '.join(session.participants)}")
    log(f"\n요약:\n{session.overall_summary}")

    if session.action_items:
        log("\n액션 아이템:")
        for item in session.action_items:
            deadline = f" ({item.deadline})" if item.deadline else ""
            log(f"  [{item.member}] {item.task}{deadline}")

    if session.next_week_plan.topics:
        log(f"\n다음 계획: {', '.join(session.next_week_plan.topics)}")
    log("=" * 60)
    log("\n[테스트] 완료!")

except Exception as e:
    import traceback
    log(f"\n[오류] {e}")
    log(traceback.format_exc())
