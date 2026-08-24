"""Deterministic hybrid prompt classification for the Codex cost router."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


@dataclass(frozen=True)
class PromptClassification:
    """Explainable semantic category and risk estimate."""

    category: str
    risk_score: float
    semantic_score: float
    signals: tuple[str, ...]

    @property
    def reason(self) -> str:
        detail = ", ".join(self.signals[:4]) or "general task"
        return (
            f"hybrid category={self.category}; risk={self.risk_score:.2f}; "
            f"semantic={self.semantic_score:.2f}; signals={detail}"
        )


RISK_PATTERNS = {
    "security": r"\b(securit|security|auth|credential|secret|rls|vulnerab|exploit)",
    "production": r"\b(production|incident|outage|indisponib|haute disponibilite)",
    "data": r"\b(rgpd|privacy|donnees? personnelles?|data leak|fuite de donnees)",
    "financial-legal": r"\b(fiscal|finance|obligataire|juridique|legal|conformite)",
    "destructive": r"\b(supprim|delete|drop|purge|migration|rollback|restauration)",
    "reliability": r"\b(intermittent|fuite memoire|memory leak|forte charge|race condition)",
}

SIMPLE_PATTERNS = {
    "small-edit": r"\b(typo|orthographe|renomm|rename|petite modification|correction mineure)",
    "short-answer": r"\b(resume|summarize|explique brievement|une phrase|documentation|readme)",
    "format": r"\b(format|reformul|translate|tradui)",
}

MEDIUM_PATTERNS = {
    "implementation": r"\b(implemente|implement|ajoute|add|refactor|test|api|docker)",
    "analysis": r"\b(analyse|compare|benchmark|diagnosti|debug)",
}

COMPLEX_PATTERNS = {
    "architecture": r"\b(architecture|systeme distribue|distributed system|multi[- ]tenant)",
    "critical": r"\b(critique|critical|plan de reprise|disaster recovery)",
    "large-scope": r"\b(end[- ]to[- ]end|de bout en bout|repository entier|entire repository)",
}


def _matches(text: str, patterns: dict[str, str]) -> list[str]:
    return [name for name, pattern in patterns.items() if re.search(pattern, text)]


def classify_prompt(prompt: str) -> PromptClassification:
    """Combine semantic intent, scope, and risk instead of relying on keywords alone."""
    text = _normalize(prompt)
    risk = _matches(text, RISK_PATTERNS)
    simple = _matches(text, SIMPLE_PATTERNS)
    medium = _matches(text, MEDIUM_PATTERNS)
    complex_signals = _matches(text, COMPLEX_PATTERNS)
    estimated_tokens = max(1, (len(prompt) + 3) // 4)

    risk_score = min(
        1.0,
        (0.50 if risk else 0.0)
        + max(0, len(risk) - 1) * 0.18
        + (0.12 if "production" in risk else 0.0),
    )
    semantic_score = min(
        1.0,
        len(complex_signals) * 0.38
        + len(medium) * 0.18
        + (0.30 if estimated_tokens > 1_500 else 0.0),
    )
    signals = tuple(risk + complex_signals + medium + simple)

    if risk_score >= 0.46 or complex_signals:
        category = "complex"
    elif estimated_tokens > 1_500 or medium:
        category = "medium"
    elif simple:
        category = "simple"
    else:
        category = "medium"
    return PromptClassification(category, risk_score, semantic_score, signals)
