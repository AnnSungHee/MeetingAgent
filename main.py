"""
MeetingAgent CLI 진입점.

사용법:
    python main.py --text "스터디 내용..."
    python main.py --audio meeting.mp3
    python main.py --audio meeting.mp3 --text "추가 메모..."
    python main.py --text "..." --outputs markdown,notion,slack
"""

import argparse
import sys
from typing import Optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI Agent 기반 스터디 회의 자동 기록",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python main.py --text "오늘 FastAPI를 공부했습니다..."
  python main.py --audio meeting.mp3
  python main.py --audio meeting.mp3 --text "추가 메모: 다음 발표자 김철수"
  python main.py --text "..." --outputs markdown,slack
        """,
    )

    input_group = parser.add_argument_group("입력 (하나 이상 필요)")
    input_group.add_argument(
        "--audio",
        metavar="파일경로",
        help="음성 파일 경로 (.mp3, .wav, .m4a 등)",
    )
    input_group.add_argument(
        "--text",
        metavar="텍스트",
        help="회의 내용 텍스트 (녹음 대체 또는 추가 메모)",
    )

    parser.add_argument(
        "--outputs",
        metavar="채널목록",
        help="출력 채널 (쉼표 구분). 예: markdown,notion,slack,kakao\n"
             "미입력 시 .env의 OUTPUT_* 설정 사용",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.audio and not args.text:
        print("오류: --audio 또는 --text 중 하나는 반드시 필요합니다.")
        print("도움말: python main.py --help")
        sys.exit(1)

    # 출력 채널 파싱
    output_overrides: Optional[list[str]] = None
    if args.outputs:
        valid_outputs = {"markdown", "notion", "slack", "kakao"}
        output_overrides = [o.strip() for o in args.outputs.split(",")]
        invalid = set(output_overrides) - valid_outputs
        if invalid:
            print(f"오류: 지원하지 않는 출력 채널: {', '.join(invalid)}")
            print(f"지원 채널: {', '.join(valid_outputs)}")
            sys.exit(1)

    # 음성 파일 처리
    transcript: Optional[str] = None
    if args.audio:
        from inputs.audio import transcribe_audio
        transcript = transcribe_audio(args.audio)

    # 텍스트 입력 처리
    supplementary_text: Optional[str] = None
    if args.text:
        from inputs.text import load_text_input
        supplementary_text = load_text_input(text=args.text)

    # Agent 실행
    from agent.core import MeetingAgent
    agent = MeetingAgent()
    session = agent.run(
        transcript=transcript,
        supplementary_text=supplementary_text,
        output_overrides=output_overrides,
    )

    # 결과 출력
    print("\n" + "=" * 50)
    print(f"스터디 날짜: {session.date}")
    print(f"참석자: {', '.join(session.participants)}")
    print(f"\n요약:\n{session.overall_summary}")

    if session.action_items:
        print("\n액션 아이템:")
        for item in session.action_items:
            deadline = f" ({item.deadline})" if item.deadline else ""
            print(f"  - [{item.member}] {item.task}{deadline}")

    if session.next_week_plan.topics:
        print(f"\n다음 주 주제: {', '.join(session.next_week_plan.topics)}")

    print("=" * 50)


if __name__ == "__main__":
    main()
