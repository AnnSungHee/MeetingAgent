from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ActionItem(BaseModel):
    member: str = Field(description="담당자 이름")
    task: str = Field(description="해야 할 일")
    deadline: Optional[str] = Field(default=None, description="기한 (예: 다음 주 화요일)")


class TopicDiscussed(BaseModel):
    title: str = Field(description="주제 제목")
    summary: str = Field(description="논의 내용 요약")
    decisions: list[str] = Field(default_factory=list, description="결정 사항 목록")


class WeeklyPlan(BaseModel):
    date: Optional[str] = Field(default=None, description="다음 스터디 예정 날짜")
    topics: list[str] = Field(default_factory=list, description="다음 주 스터디 주제 목록")
    preparation: list[str] = Field(default_factory=list, description="사전 준비 사항 목록")
    presenter: Optional[str] = Field(default=None, description="다음 주 발표자")


class MeetingSession(BaseModel):
    session_id: str = Field(description="세션 고유 ID (날짜 기반)")
    date: str = Field(description="스터디 날짜 (YYYY-MM-DD)")
    participants: list[str] = Field(description="참석자 이름 목록")
    overall_summary: str = Field(description="전체 회의 요약 (2~3문단)")
    topics_discussed: list[TopicDiscussed] = Field(description="논의된 주제 목록")
    action_items: list[ActionItem] = Field(description="참석자별 액션 아이템")
    next_week_plan: WeeklyPlan = Field(description="다음 주 스터디 계획")
    raw_transcript: Optional[str] = Field(default=None, description="원본 회의 내용")
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="처리 시각",
    )
