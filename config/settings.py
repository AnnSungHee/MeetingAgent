from typing import Optional
import shutil
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
    llm_provider: str = Field(default="codex", alias="LLM_PROVIDER")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-4-6", alias="ANTHROPIC_MODEL")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")
    codex_command: str = Field(default="codex", alias="CODEX_COMMAND")
    codex_model: Optional[str] = Field(default=None, alias="CODEX_MODEL")
    codex_reasoning_effort: str = Field(default="low", alias="CODEX_REASONING_EFFORT")
    codex_timeout_seconds: int = Field(default=600, alias="CODEX_TIMEOUT_SECONDS")
    codex_account_usage_enabled: bool = Field(
        default=True, alias="CODEX_ACCOUNT_USAGE_ENABLED"
    )
    codex_account_cache_seconds: int = Field(
        default=30, alias="CODEX_ACCOUNT_CACHE_SECONDS"
    )
    codex_account_timeout_seconds: int = Field(
        default=10, alias="CODEX_ACCOUNT_TIMEOUT_SECONDS"
    )
    codex_token_budget: Optional[int] = Field(
        default=1_000_000, alias="CODEX_TOKEN_BUDGET"
    )
    token_usage_path: str = Field(
        default="data/usage/codex.json", alias="TOKEN_USAGE_PATH"
    )

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
    max_agent_iterations: int = Field(default=10, alias="MAX_AGENT_ITERATIONS")

    def validate_llm(self) -> None:
        """실행 전 LLM API 키 존재 여부 확인."""
        if self.llm_provider not in {"anthropic", "openai", "codex"}:
            raise ValueError(
                "LLM_PROVIDER는 'anthropic', 'openai', 'codex' 중 하나여야 합니다."
            )
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
        if self.llm_provider == "codex" and not shutil.which(self.codex_command):
            raise ValueError(
                f"Codex CLI를 찾을 수 없습니다: {self.codex_command}. "
                "CODEX_COMMAND 경로 또는 Codex 설치 상태를 확인하세요."
            )

    def validate_runtime(self, active_outputs: list[str]) -> None:
        """선택된 제공자와 출력 채널에 필요한 설정을 검증한다."""
        self.validate_llm()

        # 외부 API를 호출하기 전에 누락 설정을 발견해 부분 배포를 예방한다.
        required_settings = {
            "slack": [
                ("SLACK_BOT_TOKEN", self.slack_bot_token),
                ("SLACK_CHANNEL", self.slack_channel),
            ],
            "notion": [
                ("NOTION_API_KEY", self.notion_api_key),
                ("NOTION_DATABASE_ID", self.notion_database_id),
            ],
            "kakao": [("KAKAO_WEBHOOK_URL", self.kakao_webhook_url)],
        }
        for output in active_outputs:
            missing = [name for name, value in required_settings.get(output, []) if not value]
            if missing:
                raise ValueError(
                    f"{output} 출력에 필요한 설정이 없습니다: {', '.join(missing)}"
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
