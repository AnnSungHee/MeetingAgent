"""Slack 메시지 발송 — Phase 2에서 활성화."""

from config.settings import settings


def post_to_slack(message: str) -> dict:
    """Slack 채널에 메시지 발송."""
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError

        client = WebClient(token=settings.slack_bot_token)
        response = client.chat_postMessage(
            channel=settings.slack_channel,
            text=message,
        )

        print(f"[Slack] 메시지 발송 완료: {settings.slack_channel}")
        return {"success": True, "ts": response["ts"]}
    except Exception as e:
        return {"success": False, "error": str(e)}
