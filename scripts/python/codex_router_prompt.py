"""Codex cost router: prompt responsibilities."""

from __future__ import annotations
import re
import unicodedata
from codex_prompt_classifier import classify_prompt


def clean_text(text: str) -> str:
    """Remove HTML, long comments, duplicate lines, and unnecessary whitespace."""
    text = re.sub(r"(?is)<script.*?>.*?</script>|<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<!--.*?-->", " ", text)
    text = re.sub(r"(?s)/\*.{500,}?\*/", "/* long comment removed */", text)
    text = re.sub(r"(?m)^\s*(#|//).{500,}$", r"\1 long comment removed", text)
    text = re.sub(r"<[^>]+>", " ", text)

    result: list[str] = []
    previous = ""
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if not line:
            if result and result[-1] != "":
                result.append("")
            continue
        if line == previous:
            continue
        result.append(line)
        previous = line
    return "\n".join(result).strip()


def compress_logs(text: str) -> str:
    """Collapse repetitive logs and remove noisy low-value lines."""
    lines = text.splitlines()
    result: list[str] = []
    counts: dict[str, int] = {}
    noise = re.compile(
        r"(?i)\b(debug|trace|verbose|progress|downloaded|transformed|rendering chunks)\b"
    )
    for line in lines:
        normalized = re.sub(r"\d+", "<n>", line.strip())
        if noise.search(line) and not re.search(
            r"(?i)\b(error|fail|warning|exception)\b", line
        ):
            continue
        counts[normalized] = counts.get(normalized, 0) + 1
        if counts[normalized] <= 2:
            result.append(line)
        elif counts[normalized] == 3:
            result.append(f"[repeated log lines omitted: {normalized}]")
    return "\n".join(result)


def estimate_tokens(text: str) -> int:
    """Estimate tokens conservatively without requiring a tokenizer package."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def normalize_for_matching(text: str) -> str:
    """Lowercase text and strip accents for stable keyword matching."""
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(
        character for character in normalized if not unicodedata.combining(character)
    )


def smart_truncate(text: str, max_tokens: int) -> str:
    """Keep the beginning and end of oversized context with a clear marker."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    marker = "\n\n[... context truncated by codex_cost_router ...]\n\n"
    remaining = max(0, max_chars - len(marker))
    head = int(remaining * 0.70)
    tail = remaining - head
    return text[:head].rstrip() + marker + text[-tail:].lstrip()


def classify_complexity(prompt: str) -> tuple[str, str]:
    """Classify a task from semantic intent, scope, and risk signals."""
    result = classify_prompt(prompt)
    return result.category, result.reason


def build_optimized_prompt(prompt: str, max_input_tokens: int) -> str:
    """Apply context cleanup, log compression, and intelligent truncation."""
    return smart_truncate(clean_text(compress_logs(prompt)), max_input_tokens)
