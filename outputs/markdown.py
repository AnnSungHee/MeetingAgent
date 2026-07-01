from pathlib import Path

from config.settings import settings


def save_markdown(filename: str, content: str) -> dict:
    """마크다운 파일을 data/sessions/ 디렉토리에 저장."""
    try:
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
