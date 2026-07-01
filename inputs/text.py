from typing import Optional


def load_text_input(text: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """
    텍스트 입력 처리.

    - text: CLI에서 직접 전달된 문자열
    - file_path: 텍스트 파일 경로 (향후 확장용)
    """
    if text:
        return text.strip()

    if file_path:
        from pathlib import Path
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"텍스트 파일을 찾을 수 없습니다: {file_path}")
        return path.read_text(encoding="utf-8").strip()

    raise ValueError("text 또는 file_path 중 하나는 반드시 필요합니다.")
