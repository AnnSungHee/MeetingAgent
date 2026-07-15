from pathlib import Path

from config.settings import settings
from outputs.markdown import save_markdown


def test_save_markdown_rejects_path_traversal(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))

    result = save_markdown("../outside.md", "content")

    assert result["success"] is False
    assert "파일명만" in result["error"]
    assert not (tmp_path.parent / "outside.md").exists()


def test_save_markdown_saves_plain_filename(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))

    result = save_markdown("meeting", "# 회의록")

    assert result["success"] is True
    assert (tmp_path / "meeting.md").read_text(encoding="utf-8") == "# 회의록"
