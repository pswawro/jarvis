"""SSE formatting and response parsing."""

import json
import re


def sse(event_type: str, content: str) -> str:
    """Format a Server-Sent Event."""
    return f"data: {json.dumps({'type': event_type, 'content': content})}\n\n"


def parse_sections(text: str) -> list[tuple[str, str]]:
    """Parse XML-tagged sections from model output."""
    sections = []
    for tag in ("facts", "interpretation", "hypothesis", "recommendations"):
        pattern = f"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            sections.append((tag, match.group(1).strip()))

    # If no XML tags found, treat entire text as facts
    if not sections and text.strip():
        sections.append(("facts", text.strip()))

    return sections
