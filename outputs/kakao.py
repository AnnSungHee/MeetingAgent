"""KakaoTalk 메시지 발송 — Phase 2에서 활성화."""

from config.settings import settings


def post_to_kakao(message: str) -> dict:
    """KakaoTalk Outgoing Webhook으로 메시지 발송."""
    try:
        import requests

        response = requests.post(
            url=settings.kakao_webhook_url,
            json={"text": message},
            timeout=10,
        )
        response.raise_for_status()

        print("[KakaoTalk] 메시지 발송 완료")
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
