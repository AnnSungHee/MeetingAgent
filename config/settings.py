from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM 설정
    llm_provider: str = Field(default="anthropic", alias="LLM_PROVIDER")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-4-6", alias="ANTHROPIC_MODEL")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")

    # Whisper
    whisper_model: str = Field(default="base", alias="WHISPER_MODEL")

    # 출력 채널
    output_markdown: bool = Field(default=True, alias="OUTPUT_MARKDOWN")
    output_slack: bool = Field(default=False, alias="OUTPUT_SLACK")
    output_notion: bool = Field(default=False, alias="OUTPUT_NOTION")
    output_kakao: bool = Field(default=False, alias="OUTPUT_KAKAO")

    # Slack
    slack_bot_token: Optional[str] = Field(default=None, alias="SLACK_BOT_TOKEN")
    slack_channel: str = Field(default="#study-group", alias="SLACK_CHANNEL")

    # Notion
    notion_api_key: Optional[str] = Field(default=None, alias="NOTION_API_KEY")
    notion_database_id: Optional[str] = Field(default=None, alias="NOTION_DATABASE_ID")

    # KakaoTalk
    kakao_webhook_url: Optional[str] = Field(default=None, alias="KAKAO_WEBHOOK_URL")

    # 데이터 저장
    data_dir: str = Field(default="data/sessions", alias="DATA_DIR")

    def validate_llm(self) -> None:
        """실행 전 LLM API 키 존재 여부 확인."""
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY가 설정되지 않았습니다. "
                ".env 파일에 ANTHROPIC_API_KEY=sk-ant-... 를 추가하세요."
            )
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY가 설정되지 않았습니다. "
                ".env 파일에 OPENAI_API_KEY=sk-... 를 추가하세요."
            )

    def active_outputs(self) -> list[str]:
        """활성화된 출력 채널 이름 목록 반환."""
        outputs = []
        if self.output_markdown:
            outputs.append("markdown")
        if self.output_slack:
            outputs.append("slack")
        if self.output_notion:
            outputs.append("notion")
        if self.output_kakao:
            outputs.append("kakao")
        return outputs


settings = Settings()
