import shutil
from pathlib import Path

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from leetnotes_core.leetcode.settings import leetcode_settings
from leetnotes_core.leetcode.storage.combined import CombinedQuestionRecord

from .settings import render_settings
from .utils import problems_assets_dir, problems_root, sanitized_filename

logger = structlog.get_logger(__name__)


class ImagesNotReadyError(RuntimeError):
    """Raised when a question has images but none downloaded successfully
    (or the images part hasn't run at all yet) — see
    CombinedQuestionRecord.images_populated. Rendering assumes images are
    already downloaded, so this problem is skipped rather than rendered with
    broken/missing image links."""


class LeetCodeDSAProblemMarkdownRender:
    def __init__(
        self,
        output_base: Path | str | None = None,
    ):
        self.template_dir = render_settings.TEMPLATE_DIR
        self.project_root = render_settings.PROJECT_ROOT_DIR
        self.dsa_problems_assets_dir = leetcode_settings.DSA_PROBLEMS_ASSETS_DIR

        # Priority: caller-supplied (CLI) > OUTPUT_BASE_DIR (.env) > DEFAULT_WRITE_DIR.
        self.output_base = render_settings.resolve_base_dir(output_base)

        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=select_autoescape([]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.template = self.env.get_template("leetcode_problem.md.j2")

        self.output_base.mkdir(parents=True, exist_ok=True)

    def render(self, record: CombinedQuestionRecord) -> str:
        """Renders a CombinedQuestionRecord into a Markdown string, using the
        locally-downloaded-images variant of the content — see
        CombinedQuestionRecord.images_populated for the precondition."""
        log = logger.bind(slug=record.slug)
        rendered = self.template.render(
            frontend_id=record.id,
            slug=record.slug,
            title=record.title,
            difficulty=record.difficulty,
            tags=record.tags,
            url=record.url,
            content=record.content.local_markdown,
            submission=record.submission,
        )
        log.info("markdown_rendered", has_submission=record.submission is not None)
        return rendered

    def _get_sanitized_filename(self, record: CombinedQuestionRecord) -> str:
        return sanitized_filename(record.id, record.title)

    def _copy_assets(self, record: CombinedQuestionRecord) -> None:
        """Copies this problem's downloaded images into
        <output_base>/Leetcode Problems/assets/<slug>/, matching the relative
        path baked into content.local_markdown at fetch time (see
        image_processor.py). A no-op when the question has no images."""
        if not record.has_images:
            return

        log = logger.bind(slug=record.slug)
        source_assets_dir = self.dsa_problems_assets_dir / record.slug
        target_assets_dir = problems_assets_dir(self.output_base, record.slug)

        if target_assets_dir.exists():
            shutil.rmtree(target_assets_dir)
        shutil.copytree(source_assets_dir, target_assets_dir)
        log.info(
            "assets_copied",
            source=str(source_assets_dir),
            target=str(target_assets_dir),
        )

    def save(self, record: CombinedQuestionRecord) -> Path:
        """
        Renders and saves `record` to <output_base>/Leetcode Problems/<file>.md,
        with its images (if any) copied to <output_base>/Leetcode Problems/assets/<slug>/.

        Raises ImagesNotReadyError instead of rendering if the question has
        images but none downloaded successfully yet (see
        CombinedQuestionRecord.images_populated) — there's no remote-URL
        fallback anymore, so a problem with broken/missing images is skipped
        rather than silently rendered wrong.
        """
        if not record.slug:
            raise ValueError("question slug cannot be null")

        log = logger.bind(slug=record.slug)

        if not record.images_populated:
            raise ImagesNotReadyError(
                f"images failed to download for '{record.slug}' — skipping render"
            )

        root = problems_root(self.output_base)
        root.mkdir(parents=True, exist_ok=True)

        self._copy_assets(record)

        output_file = root / self._get_sanitized_filename(record)
        output_file.write_text(self.render(record), encoding="utf-8")

        log.info("render_save_completed", path=str(output_file))
        return output_file
