"""
Whisper STT: 음성 파일 → 텍스트 변환.

openai-whisper는 로컬에서 실행되며 API 키가 필요 없음.
첫 실행 시 모델 파일을 자동 다운로드 (~150MB for 'base').
"""

from pathlib import Path

from config.settings import settings


def transcribe_audio(audio_path: str) -> str:
    """
    음성 파일을 Whisper로 변환해 텍스트 반환.

    Args:
        audio_path: 음성 파일 경로 (.mp3, .wav, .m4a, .webm 등)

    Returns:
        변환된 텍스트 전체 내용
    """
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"음성 파일을 찾을 수 없습니다: {audio_path}")

    supported = {".mp3", ".wav", ".m4a", ".webm", ".ogg", ".flac", ".mp4"}
    if path.suffix.lower() not in supported:
        raise ValueError(
            f"지원하지 않는 파일 형식: {path.suffix}. "
            f"지원 형식: {', '.join(supported)}"
        )

    print(f"[Whisper] 모델 '{settings.whisper_model}' 로딩 중... (첫 실행 시 시간이 걸릴 수 있습니다)")

    import whisper
    model = whisper.load_model(settings.whisper_model)

    print(f"[Whisper] '{path.name}' 변환 중...")
    result = model.transcribe(str(path), language="ko")

    transcript = result["text"].strip()
    print(f"[Whisper] 완료. 총 {len(transcript)}자 변환됨.\n")

    return transcript
