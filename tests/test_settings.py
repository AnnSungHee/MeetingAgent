import pytest

from config.settings import Settings


def test_validate_runtime_rejects_missing_slack_token() -> None:
    settings = Settings(LLM_PROVIDER="openai", OPENAI_API_KEY="test-key")

    with pytest.raises(ValueError, match="SLACK_BOT_TOKEN"):
        settings.validate_runtime(["slack"])


def test_validate_runtime_accepts_configured_kakao() -> None:
    settings = Settings(
        LLM_PROVIDER="openai",
        OPENAI_API_KEY="test-key",
        KAKAO_WEBHOOK_URL="https://example.com/webhook",
    )

    settings.validate_runtime(["kakao"])
