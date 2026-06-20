#!/usr/bin/env python3
"""Rule-based evaluator for finance security and algorithmic-bias reviews."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    """A deterministic rule finding."""

    code: str
    severity: float
    message: str


RISK_PATTERNS: tuple[tuple[str, str, float, str], ...] = (
    (
        "protected_attribute",
        r"\b(age|gender|sex|race|ethnicity|religion|nationality|disability|marital status|postal code|zip code)\b",
        0.95,
        "usage potentiel d'attribut protégé ou proxy discriminatoire",
    ),
    (
        "unbounded_automation",
        r"\b(auto[- ]?approve|automatic approval|fully automated|no human review|without human intervention)\b",
        0.90,
        "décision financière automatisée sans contrôle humain explicite",
    ),
    (
        "no_auditability",
        r"\bblack box|opaque model|no logs?|without audit|no audit trail|untraceable\b",
        0.90,
        "auditabilité ou traçabilité insuffisante",
    ),
    (
        "security_secret",
        r"\b(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}",
        0.95,
        "secret ou identifiant technique potentiellement exposé",
    ),
    (
        "unsupported_guarantee",
        r"\bguarantee(?:d)?\b|\b100%\b|\bmathematically certain\b|\bno bias\b",
        0.85,
        "garantie absolue non démontrable dans un système algorithmique",
    ),
    (
        "hallucinated_interface",
        r"\b(call_magic_model|detect_all_bias|guarantee_fairness|remove_all_bias|perfect_explainability)\b",
        0.80,
        "fonction ou capacité probablement hallucinee/non spécifiée",
    ),
    (
        "financial_exclusion",
        r"\b(reject|deny|exclude|blacklist)\b.*\b(low income|unemployed|immigrant|neighbourhood|neighborhood)\b",
        0.95,
        "risque d'exclusion financière ou de discrimination indirecte",
    ),
)

REQUIRED_CONTROLS: tuple[tuple[str, str, str], ...] = (
    (
        "fairness_metrics",
        r"\b(fairness|bias|disparate impact|equal opportunity|demographic parity|equalized odds)\b",
        "absence de métriques ou critères de fairness",
    ),
    (
        "human_review",
        r"\b(human review|manual review|appeal|contest|override|second line review)\b",
        "absence de revue humaine ou mécanisme de contestation",
    ),
    (
        "audit_logging",
        r"\b(audit|log|traceability|monitoring|model card|decision record)\b",
        "absence d'auditabilité ou de journalisation",
    ),
    (
        "data_governance",
        r"\b(data quality|data governance|lineage|consent|privacy|gdpr|retention)\b",
        "absence de gouvernance des données",
    ),
    (
        "security_controls",
        r"\b(encryption|access control|least privilege|secret management|rate limit|authentication)\b",
        "absence de contrôles de sécurité explicites",
    ),
)


def normalize(text: str) -> str:
    """Normalize whitespace for deterministic rule matching."""

    return re.sub(r"\s+", " ", text).strip()


def evaluate(text: str) -> dict[str, object]:
    """Evaluate a proposal and return the required JSON-compatible object."""

    proposal = normalize(text)
    findings: list[Finding] = []

    if not proposal:
        findings.append(Finding("empty_input", 1.0, "proposition vide ou non fournie"))

    lowered = proposal.casefold()

    for code, pattern, severity, message in RISK_PATTERNS:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            findings.append(Finding(code, severity, message))

    for code, pattern, message in REQUIRED_CONTROLS:
        if not re.search(pattern, lowered, flags=re.IGNORECASE):
            findings.append(Finding(code, 0.70, message))

    if findings:
        top = max(findings, key=lambda item: item.severity)
        confidence = min(
            0.99,
            0.55 + max(item.severity for item in findings) * 0.35 + len(findings) * 0.02,
        )
        return {
            "statut": 0,
            "confiance": round(confidence, 2),
            "justification_technique": (
                f"{top.message}; {len(findings)} point(s) de risque ou de contrôle manquant détecté(s)."
            ),
        }

    return {
        "statut": 1,
        "confiance": 0.78,
        "justification_technique": (
            "Aucun biais, hallucination d'interface ou manque critique de contrôle détecté par les règles statiques."
        ),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Evaluate finance security and algorithmic-bias risks and print strict JSON."
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Optional UTF-8 file containing the technical proposal. Reads stdin when omitted.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON for manual review. The default is compact JSON.",
    )
    return parser.parse_args(argv)


def read_input(path: str | None) -> str:
    """Read the proposal from a file or stdin."""

    if path:
        return Path(path).read_text(encoding="utf-8")
    return sys.stdin.read()


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    args = parse_args(argv or sys.argv[1:])
    result = evaluate(read_input(args.file))
    output = json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
