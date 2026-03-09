"""Text utility functions for LLM-generated content normalization."""
from __future__ import annotations

import re
import unicodedata


def normalize_content(text: str) -> str:
    """Normalize LLM-generated markdown content.

    - Remove non-printable / non-standard Unicode control characters
    - Strip trailing whitespace from each line
    - Collapse 3+ consecutive blank lines to 2
    """
    # Remove C0/C1 control characters except newline and tab
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)

    # Remove Unicode "Cf" format chars (zero-width space, BOM, soft hyphen, etc.)
    cleaned = "".join(
        ch for ch in cleaned
        if unicodedata.category(ch) != "Cf" or ch in {"\t", "\n"}
    )

    # Strip trailing whitespace per line
    lines = [line.rstrip() for line in cleaned.splitlines()]

    # Collapse 3+ consecutive blank lines → 2
    result: list[str] = []
    blank_count = 0
    for line in lines:
        if line == "":
            blank_count += 1
            if blank_count <= 2:
                result.append(line)
        else:
            blank_count = 0
            result.append(line)

    return "\n".join(result)
