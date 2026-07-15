"""구조화된 회의 요약으로 출력 채널별 payload를 생성한다.

동일 내용을 LLM이 채널마다 다시 생성하지 않도록 하여 출력 토큰을 줄인다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def build_output_tool_inputs(
    summary: dict[str, Any], tool_names: list[str]
) -> dict[str, dict[str, Any]]:
    date = datetime.now().strftime("%Y-%m-%d")
    markdown = render_markdown(summary, date)
    payloads: dict[str, dict[str, Any]] = {
        "save_session_summary": summary,
        "save_markdown": {
            "filename": f"{date}-study.md",
            "content": markdown,
        },
        "create_notion_page": {
            "title": f"{date} 스터디 회의록",
            "content": markdown,
        },
        "post_to_slack": {"message": render_short_message(summary, date, slack=True)},
        "post_to_kakao": {"message": render_short_message(summary, date, slack=False)},
    }
    return {name: payloads[name] for name in tool_names}


def render_markdown(summary: dict[str, Any], date: str) -> str:
    participants = ", ".join(summary.get("participants", [])) or "없음"
    lines = [
        f"# {date} 스터디 회의록",
        "",
        "## 참석자",
        participants,
        "",
        "## 전체 요약",
        summary.get("overall_summary", ""),
        "",
        "## 주요 내용",
    ]
    topics = summary.get("topics_discussed", [])
    if not topics:
        lines.append("- 논의된 주제 없음")
    for topic in topics:
        lines.extend(["", f"### {topic['title']}", topic["summary"]])
        decisions = topic.get("decisions", [])
        if decisions:
            lines.append("결정 사항:")
            lines.extend(f"- {decision}" for decision in decisions)

    lines.extend(["", "## 액션 아이템"])
    action_items = summary.get("action_items", [])
    if action_items:
        for item in action_items:
            deadline = f" ({item['deadline']})" if item.get("deadline") else ""
            lines.append(f"- **{item['member']}**: {item['task']}{deadline}")
    else:
        lines.append("- 없음")

    plan = summary.get("next_week_plan", {})
    lines.extend(["", "## 다음 주 계획"])
    if plan.get("date"):
        lines.append(f"- 일정: {plan['date']}")
    if plan.get("topics"):
        lines.append(f"- 주제: {', '.join(plan['topics'])}")
    if plan.get("preparation"):
        lines.append(f"- 준비: {', '.join(plan['preparation'])}")
    if plan.get("presenter"):
        lines.append(f"- 발표자: {plan['presenter']}")
    if not any(plan.get(key) for key in ("date", "topics", "preparation", "presenter")):
        lines.append("- 미정")
    return "\n".join(lines).strip() + "\n"


def render_short_message(summary: dict[str, Any], date: str, slack: bool) -> str:
    title = f"*{date} 스터디 요약*" if slack else f"{date} 스터디 요약"
    lines = [title, summary.get("overall_summary", "").strip()]
    plan_topics = summary.get("next_week_plan", {}).get("topics", [])
    if plan_topics:
        label = "*다음 주*" if slack else "다음 주"
        lines.append(f"{label}: {', '.join(plan_topics)}")
    action_items = summary.get("action_items", [])
    if action_items:
        label = "*액션 아이템*" if slack else "액션 아이템"
        lines.append(label)
        lines.extend(f"- {item['member']}: {item['task']}" for item in action_items)
    return "\n".join(line for line in lines if line)
