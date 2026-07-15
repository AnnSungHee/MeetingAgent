from pathlib import Path

from config.settings import settings


def save_markdown(filename: str, content: str) -> dict:
    """마크다운 파일을 data/sessions/ 디렉토리에 저장."""
    try:
        candidate = Path(filename)
        # 파일명은 LLM이 생성하므로 data_dir 밖으로 나가는 경로를 신뢰하지 않는다.
        if not filename or candidate.is_absolute() or candidate.name != filename:
            raise ValueError("파일명만 사용할 수 있습니다. 경로는 포함할 수 없습니다.")

        data_dir = Path(settings.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)

        # 파일명에 .md 확장자 없으면 추가
        if not filename.endswith(".md"):
            filename = f"{filename}.md"

        output_path = data_dir / filename
        output_path.write_text(content, encoding="utf-8")

        print(f"[Markdown] 저장 완료: {output_path}")
        return {"success": True, "path": str(output_path)}
    except Exception as e:
        return {"success": False, "error": str(e)}
