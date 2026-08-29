"""
One-off fix: regenerates content_local_html/content_local_markdown for every
already-fetched problem with images, purely from its already-stored
raw_question_html and the images already downloaded under
LEETCODE_DATA/dsa_problems/assets/<slug>/ — no network calls, nothing is
re-downloaded (LeetCodeImageProcessor.download_single_image skips any image
already cached at its expected path).

Needed because the relative image path baked into that content changed (see
modules/leetcode/image_processor.py) when the rendered output layout
flattened from Leetcode Problems/local/<slug>/assets/ to
Leetcode Problems/assets/<slug>/.

Safe to re-run — every run just recomputes the same content from the same
inputs.

Run once: uv run python -m scripts.rebake_local_image_paths
"""

from modules.leetcode import parsers
from modules.leetcode.image_processor import LeetCodeImageProcessor
from modules.leetcode.storage import LeetCodeDSAStorage


def main() -> None:
    storage = LeetCodeDSAStorage()
    image_processor = LeetCodeImageProcessor()

    records = [r for r in storage.problems_list_all() if r.has_images]
    print(f"Found {len(records)} problem(s) with images to rebake.")

    updated = 0
    for record in records:
        result = image_processor.process_question_images(record)
        if result["content_local_html"] is None:
            print(f"  [skip] {record.slug}: no valid <img> tags found on re-parse")
            continue
        record.content.local_html = result["content_local_html"]
        record.content.local_markdown = parsers.html_to_markdown(
            result["content_local_html"]
        )
        storage.problems_add_or_update(record)
        updated += 1
        print(f"  [done] {record.slug}")

    print(f"Rebaked {updated}/{len(records)} problem(s).")


if __name__ == "__main__":
    main()
