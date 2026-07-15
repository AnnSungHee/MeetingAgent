import pytest

from config.settings import Settings


def test_default_provider_is_codex() -> None:
    settings = Settings(_env_file=None)

    assert settings.llm_provider == "codex"


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


def test_codex_provider_does_not_require_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("config.settings.shutil.which", lambda _: "/usr/bin/codex")
    settings = Settings(LLM_PROVIDER="codex")

    settings.validate_llm()
