"""Notion API 연동 — Phase 2에서 활성화."""

from config.settings import settings


def create_notion_page(title: str, content: str) -> dict:
    """Notion 데이터베이스에 회의 요약 페이지 생성."""
    try:
        from notion_client import Client

        client = Client(auth=settings.notion_api_key)

        # 마크다운을 Notion 블록으로 변환 (단순 텍스트 처리)
        blocks = _markdown_to_blocks(content)

        page = client.pages.create(
            parent={"database_id": settings.notion_database_id},
            properties={
                "Name": {"title": [{"text": {"content": title}}]},
            },
            children=blocks,
        )

        page_url = page.get("url", "")
        print(f"[Notion] 페이지 생성 완료: {page_url}")
        return {"success": True, "url": page_url}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _markdown_to_blocks(markdown: str) -> list[dict]:
    """마크다운 텍스트를 Notion 블록 목록으로 변환 (기본 변환)."""
    blocks = []
    for line in markdown.split("\n"):
        line = line.rstrip()
        if not line:
            continue
        elif line.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": line[3:]}}]},
            })
        elif line.startswith("### "):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": [{"type": "text", "text": {"content": line[4:]}}]},
            })
        elif line.startswith("- "):
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": line[2:]}}]},
            })
        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": line}}]},
            })
    return blocks
