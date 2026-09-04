from enum import StrEnum
from pathlib import Path


class NotesStyle(StrEnum):
    PLAIN = "plain"  # Plain Markdown, no Obsidian syntax
    OBSIDIAN = "obsidian"  # Obsidian wikilinks + callouts
    PLAIN_AI = "plain+ai"  # Plain + AI-prefilled content
    OBSIDIAN_AI = "obsidian+ai"  # Obsidian + AI-prefilled content


# Base style -> its '+ai' variant. The CLI exposes style/--ai as two
# independent choices; this is the one place they're combined into the
# NotesStyle the renderer actually understands.
AI_STYLE = {
    NotesStyle.PLAIN: NotesStyle.PLAIN_AI,
    NotesStyle.OBSIDIAN: NotesStyle.OBSIDIAN_AI,
}


def sanitized_filename(frontend_id: int | None, title: str | None) -> str:
    """Generates the shared OS-safe Markdown filename `<id> - <title>.md` used by every renderer."""
    raw_name = f"{frontend_id or 0:04d} - {title}.md"
    return "".join(
        c for c in raw_name if c.isalnum() or c in (" ", "-", "_", ".")
    ).rstrip()


def problems_root(base: Path) -> Path:
    """<base>/Leetcode Problems — flat: one <file>.md per problem directly in
    here (no per-problem subfolder), plus a shared assets/ dir (see
    problems_assets_dir)."""
    return base / "Leetcode Problems"


def problems_assets_dir(base: Path, slug: str) -> Path:
    """<base>/Leetcode Problems/assets/<slug> — this problem's downloaded
    images, addressed by every problem file via the relative path
    'assets/<slug>/<file>' baked into content.local_markdown/local_html at
    fetch time (see modules/leetcode/image_processor.py)."""
    return problems_root(base) / "assets" / slug


def notes_root(base: Path) -> Path:
    """<base>/Leetcode Notes — root for the single, style-agnostic notes file per problem."""
    return base / "Leetcode Notes"
