from __future__ import annotations

import re

_MULTI_SPACE = re.compile(r"\s+")



def clean_text(value: object) -> str | None:
    """Trim and normalize whitespace; return None for empty values."""

    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    text = _MULTI_SPACE.sub(" ", text)
    return text
