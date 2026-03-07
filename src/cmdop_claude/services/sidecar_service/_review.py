"""Sidecar review — generate review, write review.md."""
import hashlib
from datetime import datetime, timezone
from typing import Optional

from ...models.sidecar import (
    DocScanResult,
    LLMReviewItem,
    LLMReviewResponse,
    ReviewItem,
    ReviewResult,
)
from ...sidecar.prompts import REVIEW_SYSTEM, REVIEW_USER


class ReviewMixin:
    """Documentation review: scan → LLM → review.md."""

    def generate_review(
        self, scan_result: Optional[DocScanResult] = None
    ) -> ReviewResult:
        """Send scan data to LLM, produce review, write review.md."""
        if not self._acquire_lock():
            raise RuntimeError("Sidecar is already running (lock held)")

        try:
            if scan_result is None:
                scan_result = self.scan()

            self._ensure_dirs()
            suppressed = self._load_suppressed()

            files_block = "\n".join(
                f"- {f.path} | modified: {f.modified_at.isoformat()} | {f.line_count} lines | {f.summary or '(no summary)'}"
                for f in scan_result.files
            )

            contents_block = self._build_contents_block(scan_result)

            commits_block = (
                "\n".join(scan_result.recent_commits) or "(no git history)"
            )
            deps_block = ", ".join(scan_result.dependencies) or "(none detected)"
            dirs_block = ", ".join(scan_result.top_dirs) or "(none)"
            suppressed_block = (
                ", ".join(suppressed.keys()) or "(none)"
            )

            user_msg = REVIEW_USER.format(
                files_block=files_block,
                contents_block=contents_block,
                commits_block=commits_block,
                deps_block=deps_block,
                dirs_block=dirs_block,
                suppressed_block=suppressed_block,
            )

            response = self._sdk.parse(
                model=self._model,
                messages=[
                    {"role": "system", "content": REVIEW_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                response_format=LLMReviewResponse,
                temperature=0.2,
            )

            tokens_used = response.usage.total_tokens if response.usage else 0
            model_used = response.model or "unknown"

            parsed: Optional[LLMReviewResponse] = response.choices[0].message.parsed
            llm_items = parsed.items if parsed else []

            items = self._build_items(llm_items, suppressed)

            now = datetime.now(tz=timezone.utc)
            result = ReviewResult(
                generated_at=now,
                items=items,
                tokens_used=tokens_used,
                model_used=model_used,
            )

            self._write_review_md(result)
            self._archive_review(now.isoformat())
            self._track_usage(tokens_used)
            self._log_activity(
                "review", tokens=tokens_used, model=model_used,
                items_found=len(result.items),
            )

            return result
        finally:
            self._release_lock()

    def _build_items(
        self, llm_items: list[LLMReviewItem], suppressed: dict[str, str]
    ) -> list[ReviewItem]:
        items: list[ReviewItem] = []
        for entry in llm_items:
            item_id = hashlib.md5(
                (entry.description + str(entry.affected_files)).encode()
            ).hexdigest()[:12]

            if item_id in suppressed:
                continue

            items.append(
                ReviewItem(
                    category=entry.category,
                    severity=entry.severity,
                    description=entry.description,
                    affected_files=entry.affected_files,
                    suggested_action=entry.suggested_action,
                    item_id=item_id,
                )
            )
        return items

    def _build_contents_block(self, scan_result: DocScanResult) -> str:
        """Read full text of each doc file for contradiction detection."""
        parts: list[str] = []
        for f in scan_result.files:
            fpath = self._claude_dir.parent / f.path
            if not fpath.exists():
                continue
            try:
                text = fpath.read_text(encoding="utf-8")
                if len(text) > 2000:
                    text = text[:2000] + "\n... (truncated)"
                parts.append(f"### {f.path}\n```\n{text}\n```")
            except Exception:
                continue
        return "\n\n".join(parts) or "(no file contents available)"

    # ── Review.md rendering ───────────────────────────────────────────

    def _write_review_md(self, result: ReviewResult) -> None:
        lines = [f"# Sidecar Review -- {result.generated_at.isoformat()}", ""]

        by_cat: dict[str, list[ReviewItem]] = {}
        for item in result.items:
            by_cat.setdefault(item.category, []).append(item)

        section_titles = {
            "staleness": "Staleness",
            "contradiction": "Contradictions",
            "gap": "Missing Documentation",
            "abandoned_plan": "Abandoned Plans",
        }

        for cat, title in section_titles.items():
            cat_items = by_cat.get(cat, [])
            if not cat_items:
                continue
            lines.append(f"## {title}")
            lines.append("")
            for item in cat_items:
                sev = {"high": "[!]", "medium": "[?]", "low": "[~]"}.get(
                    item.severity, "[?]"
                )
                lines.append(f"- {sev} {item.description}")
                if item.affected_files:
                    lines.append(f"  Files: {', '.join(item.affected_files)}")
                lines.append(f"  Action: {item.suggested_action}")
                lines.append(f"  (id: {item.item_id})")
                lines.append("")

        if not result.items:
            lines.append("No issues found. Documentation looks consistent.")
            lines.append("")

        lines.append("---")
        lines.append(
            f"Model: {result.model_used} | Tokens: {result.tokens_used}"
        )

        review_path = self._sidecar_dir / "review.md"
        review_path.write_text("\n".join(lines), encoding="utf-8")

    def _archive_review(self, timestamp: str) -> None:
        review_path = self._sidecar_dir / "review.md"
        if not review_path.exists():
            return
        date_str = timestamp[:10]
        history_dir = self._sidecar_dir / "history"
        history_dir.mkdir(exist_ok=True)
        archive_path = history_dir / f"{date_str}.md"
        archive_path.write_text(
            review_path.read_text(encoding="utf-8"), encoding="utf-8"
        )

    def get_current_review(self) -> str:
        """Return current review.md content, or empty string if none."""
        review_path = self._sidecar_dir / "review.md"
        if review_path.exists():
            return review_path.read_text(encoding="utf-8")
        return ""
