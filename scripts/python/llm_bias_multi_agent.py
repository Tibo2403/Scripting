#!/usr/bin/env python3
"""Generic multi-agent prompt-return manager for LLM outputs.

The module is intentionally dependency-free. It can be used as a post-processing
layer after any LLM provider: pass the original prompt and model answer, then
receive a managed multi-agent review, a revised answer, and a structured report.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    """One issue raised by a review agent."""

    agent: str
    code: str
    severity: float
    span: str
    recommendation: str


@dataclass(frozen=True)
class AgentReport:
    """Findings produced by one specialist agent."""

    agent: str
    findings: tuple[Finding, ...]


@dataclass(frozen=True)
class ManagerRound:
    """One manager review/revision pass."""

    round_index: int
    input_answer: str
    revised_answer: str
    risk_score: float
    status: str
    reports: tuple[AgentReport, ...]


class ReviewAgent:
    """Base class for deterministic review agents."""

    name = "base"

    def review(self, prompt: str, answer: str) -> AgentReport:
        raise NotImplementedError


def normalize_spaces(text: str) -> str:
    """Collapse whitespace without changing words."""

    return re.sub(r"\s+", " ", text).strip()


def snippet(text: str, start: int, end: int, max_len: int = 90) -> str:
    """Return a compact excerpt around a regex match."""

    value = normalize_spaces(text[start:end])
    if len(value) <= max_len:
        return value
    return value[: max_len - 3].rstrip() + "..."


def strip_manager_notes(text: str) -> str:
    """Remove notes previously appended by this manager before a new revision."""

    return re.split(r"\n\nBias-mitigation notes:\n", text, maxsplit=1)[0].strip()


class ProtectedAttributeAgent(ReviewAgent):
    """Detects protected attributes used as broad explanations."""

    name = "protected_attribute_agent"
    patterns: tuple[tuple[str, str], ...] = (
        ("age", r"\b(age|old people|young people|teenagers|elderly)\b"),
        ("gender", r"\b(gender|men|women|male|female|boys|girls)\b"),
        ("origin", r"\b(race|ethnicity|nationality|immigrant|foreigners?)\b"),
        ("religion", r"\b(religion|muslim|christian|jewish|hindu)\b"),
        ("disability", r"\b(disability|disabled|neurodivergent)\b"),
        ("socioeconomic", r"\b(poor people|low income|rich people|working class)\b"),
    )

    def review(self, prompt: str, answer: str) -> AgentReport:
        findings: list[Finding] = []
        for code, pattern in self.patterns:
            for match in re.finditer(pattern, answer, flags=re.IGNORECASE):
                findings.append(
                    Finding(
                        self.name,
                        f"protected_attribute_{code}",
                        0.72,
                        snippet(answer, match.start(), match.end()),
                        "Avoid using protected or sensitive attributes as a broad causal shortcut.",
                    )
                )
        return AgentReport(self.name, tuple(findings))


class StereotypeAgent(ReviewAgent):
    """Detects broad claims and stereotype-like phrasing."""

    name = "stereotype_agent"
    patterns: tuple[tuple[str, str, float, str], ...] = (
        (
            "group_generalization",
            r"\b(all|always|never|everyone|nobody|most|typical|naturally|inherently)\b.{0,80}\b(people|users|customers|patients|employees|men|women|immigrants|students)\b",
            0.82,
            "Replace broad group claims with scoped, evidence-based language.",
        ),
        (
            "deficit_framing",
            r"\b(lazy|irrational|untrustworthy|aggressive|bad at|not suited|cannot handle|less capable)\b",
            0.86,
            "Remove deficit framing unless it is supported by specific, relevant evidence.",
        ),
        (
            "culture_essentialism",
            r"\b(culture makes them|because of their culture|born to|naturally better|naturally worse)\b",
            0.88,
            "Avoid essentialist explanations for behavior or capability.",
        ),
    )

    def review(self, prompt: str, answer: str) -> AgentReport:
        findings: list[Finding] = []
        for code, pattern, severity, recommendation in self.patterns:
            for match in re.finditer(pattern, answer, flags=re.IGNORECASE):
                findings.append(
                    Finding(
                        self.name,
                        code,
                        severity,
                        snippet(answer, match.start(), match.end()),
                        recommendation,
                    )
                )
        return AgentReport(self.name, tuple(findings))


class EvidenceAgent(ReviewAgent):
    """Detects overconfident claims without uncertainty markers."""

    name = "evidence_agent"
    unsupported_patterns: tuple[tuple[str, str], ...] = (
        ("certainty", r"\b(proves|guarantees|certainly|without doubt|100%|completely unbiased|no bias)\b"),
        ("universal_policy", r"\b(best for everyone|works for all|one-size-fits-all|universally optimal)\b"),
    )

    def review(self, prompt: str, answer: str) -> AgentReport:
        findings: list[Finding] = []
        for code, pattern in self.unsupported_patterns:
            for match in re.finditer(pattern, answer, flags=re.IGNORECASE):
                findings.append(
                    Finding(
                        self.name,
                        f"unsupported_{code}",
                        0.70,
                        snippet(answer, match.start(), match.end()),
                        "Add uncertainty, evidence requirements, and limits of applicability.",
                    )
                )
        return AgentReport(self.name, tuple(findings))


class InclusionAgent(ReviewAgent):
    """Detects missing alternatives or asymmetric framing."""

    name = "inclusion_agent"

    def review(self, prompt: str, answer: str) -> AgentReport:
        lowered = answer.casefold()
        findings: list[Finding] = []
        if any(word in lowered for word in ("should reject", "should exclude", "should avoid hiring", "deny access")):
            findings.append(
                Finding(
                    self.name,
                    "exclusionary_recommendation",
                    0.84,
                    "exclusionary recommendation",
                    "Prefer least-restrictive alternatives, review paths, and context-specific criteria.",
                )
            )
        if "alternative" not in lowered and "exception" not in lowered and "review" not in lowered:
            findings.append(
                Finding(
                    self.name,
                    "missing_alternatives",
                    0.45,
                    "no alternatives or review path",
                    "Mention alternatives, exceptions, or human review when making consequential recommendations.",
                )
            )
        return AgentReport(self.name, tuple(findings))


class SafetyAgent(ReviewAgent):
    """Detects sensitive decision contexts that require stronger safeguards."""

    name = "safety_agent"
    consequential_context = re.compile(
        r"\b(loan|credit|insurance|hiring|medical|diagnosis|housing|school admission|policing|benefit|welfare)\b",
        flags=re.IGNORECASE,
    )

    def review(self, prompt: str, answer: str) -> AgentReport:
        combined = f"{prompt}\n{answer}"
        if not self.consequential_context.search(combined):
            return AgentReport(self.name, ())

        lowered = answer.casefold()
        findings: list[Finding] = []
        required_terms = (
            ("human_review", ("human review", "manual review", "appeal", "contest", "override")),
            ("auditability", ("audit", "log", "trace", "monitor", "record")),
            ("fairness_testing", ("fairness", "bias", "disparate impact", "equal opportunity")),
        )
        for code, terms in required_terms:
            if not any(term in lowered for term in terms):
                findings.append(
                    Finding(
                        self.name,
                        f"missing_{code}",
                        0.76,
                        "consequential decision without safeguard",
                        f"Add {code.replace('_', ' ')} before using this output in a consequential context.",
                    )
                )
        return AgentReport(self.name, tuple(findings))


class BiasReducer:
    """Backward-compatible facade for the generic prompt manager."""

    def __init__(self, agents: tuple[ReviewAgent, ...] | None = None) -> None:
        self.manager = MultiAgentPromptManager(agents=agents)
        self.agents = self.manager.agents

    def evaluate(self, prompt: str, answer: str) -> dict[str, object]:
        """Return a structured multi-agent bias review."""

        return self.manager.evaluate(prompt, answer)

    def revise(self, answer: str, findings: tuple[Finding, ...]) -> str:
        """Apply conservative debiasing rewrites without inventing facts."""

        return self.manager.revise(answer, findings)


class MultiAgentPromptManager:
    """Standard manager for generic LLM prompt returns.

    The manager has no dependency on a domain such as finance. Its job is to:
    collect review-agent feedback, aggregate risk, revise the answer
    conservatively, and optionally repeat the process for several rounds.
    """

    def __init__(
        self,
        agents: tuple[ReviewAgent, ...] | None = None,
        max_rounds: int = 1,
        stop_risk_score: float = 0.0,
    ) -> None:
        self.agents = agents or default_review_agents()
        self.max_rounds = max(1, max_rounds)
        self.stop_risk_score = max(0.0, min(1.0, stop_risk_score))

    def evaluate(self, prompt: str, answer: str, max_rounds: int | None = None) -> dict[str, object]:
        """Run managed review/revision rounds for one LLM answer."""

        rounds = self.run_rounds(prompt, answer, max_rounds=max_rounds)
        final_round = rounds[-1]
        findings = tuple(finding for report in final_round.reports for finding in report.findings)
        return {
            "manager": "multi_agent_prompt_manager",
            "round_count": len(rounds),
            "risk_score": final_round.risk_score,
            "status": final_round.status,
            "finding_count": len(findings),
            "agent_reports": [
                {
                    "agent": report.agent,
                    "findings": [asdict(finding) for finding in report.findings],
                }
                for report in final_round.reports
            ],
            "rounds": [self._round_to_dict(round_result) for round_result in rounds],
            "revised_answer": final_round.revised_answer,
        }

    def run_rounds(self, prompt: str, answer: str, max_rounds: int | None = None) -> tuple[ManagerRound, ...]:
        """Return each review/revision pass as structured objects."""

        limit = max(1, max_rounds if max_rounds is not None else self.max_rounds)
        current_answer = answer.strip()
        rounds: list[ManagerRound] = []
        for round_index in range(1, limit + 1):
            reports = tuple(agent.review(prompt, current_answer) for agent in self.agents)
            findings = tuple(finding for report in reports for finding in report.findings)
            risk_score = self._risk_score(findings)
            revised_answer = self.revise(current_answer, findings)
            status = "needs_revision" if findings else "accepted"
            round_result = ManagerRound(
                round_index=round_index,
                input_answer=current_answer,
                revised_answer=revised_answer,
                risk_score=risk_score,
                status=status,
                reports=reports,
            )
            rounds.append(round_result)
            current_answer = revised_answer
            if risk_score <= self.stop_risk_score or revised_answer == round_result.input_answer:
                break
        return tuple(rounds)

    def review_once(self, prompt: str, answer: str) -> tuple[AgentReport, ...]:
        """Run agents without applying a revision."""

        reports = tuple(agent.review(prompt, answer) for agent in self.agents)
        return reports

    def revise(self, answer: str, findings: tuple[Finding, ...]) -> str:
        """Apply conservative generic rewrites without inventing new facts."""

        if not findings:
            return answer.strip()

        revised = strip_manager_notes(answer)
        replacements = (
            (r"\bshould reject them\b", "should route them to documented review", re.IGNORECASE),
            (r"\bshould exclude them\b", "should assess them with documented criteria", re.IGNORECASE),
            (r"\ball\b", "some", re.IGNORECASE),
            (r"\balways\b", "may sometimes", re.IGNORECASE),
            (r"\bnever\b", "may not always", re.IGNORECASE),
            (r"\beveryone\b", "many people", re.IGNORECASE),
            (r"\bnobody\b", "not everyone", re.IGNORECASE),
            (r"\bwill certainly\b", "may", re.IGNORECASE),
            (r"\bcertainly\b", "may", re.IGNORECASE),
            (r"\bwithout doubt\b", "with supporting evidence", re.IGNORECASE),
            (r"\bguarantees?\b", "may support", re.IGNORECASE),
            (r"\bproves?\b", "may suggest", re.IGNORECASE),
            (r"\b100%\b", "highly", re.IGNORECASE),
            (r"\bcompletely unbiased\b", "designed to reduce measured bias", re.IGNORECASE),
            (r"\bno bias\b", "lower measured bias", re.IGNORECASE),
            (r"\bshould reject\b", "should review carefully", re.IGNORECASE),
            (r"\bshould exclude\b", "should assess with documented criteria", re.IGNORECASE),
        )
        for pattern, replacement, flags in replacements:
            revised = re.sub(pattern, replacement, revised, flags=flags)

        notes = self._mitigation_notes(findings)
        if notes:
            revised = f"{revised}\n\nBias-mitigation notes:\n" + "\n".join(f"- {note}" for note in notes)
        return revised

    @staticmethod
    def _risk_score(findings: tuple[Finding, ...]) -> float:
        if not findings:
            return 0.0
        combined = 1.0
        for finding in findings:
            combined *= 1.0 - min(max(finding.severity, 0.0), 1.0) * 0.35
        return round(min(1.0, 1.0 - combined), 3)

    @staticmethod
    def _mitigation_notes(findings: tuple[Finding, ...]) -> list[str]:
        notes: list[str] = []
        recommendations = []
        for finding in sorted(findings, key=lambda item: item.severity, reverse=True):
            if finding.recommendation not in recommendations:
                recommendations.append(finding.recommendation)
        for recommendation in recommendations[:5]:
            notes.append(recommendation)
        if findings:
            notes.append("Validate remaining claims with task-specific data, subgroup metrics, and human review.")
        return notes

    @staticmethod
    def _round_to_dict(round_result: ManagerRound) -> dict[str, object]:
        findings = tuple(finding for report in round_result.reports for finding in report.findings)
        return {
            "round_index": round_result.round_index,
            "risk_score": round_result.risk_score,
            "status": round_result.status,
            "finding_count": len(findings),
            "revised_answer": round_result.revised_answer,
        }


def default_review_agents() -> tuple[ReviewAgent, ...]:
    """Return the standard generic LLM-output review panel."""

    return (
        ProtectedAttributeAgent(),
        StereotypeAgent(),
        EvidenceAgent(),
        InclusionAgent(),
        SafetyAgent(),
    )


def read_text(path: str | None) -> str:
    """Read text from a UTF-8 file or stdin."""

    if path:
        return Path(path).read_text(encoding="utf-8")
    return sys.stdin.read()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage generic LLM prompt returns using deterministic multi-agent review."
    )
    parser.add_argument("answer_file", nargs="?", help="UTF-8 file containing the LLM answer. Reads stdin if omitted.")
    parser.add_argument("--prompt-file", help="Optional UTF-8 file containing the original prompt.")
    parser.add_argument("--prompt", default="", help="Optional original prompt text.")
    parser.add_argument("--text", help="LLM answer text. Overrides answer_file/stdin when provided.")
    parser.add_argument("--max-rounds", type=int, default=1, help="Maximum manager review/revision rounds.")
    parser.add_argument(
        "--stop-risk-score",
        type=float,
        default=0.0,
        help="Stop early when the round risk score is at or below this value.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the JSON report.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    prompt = read_text(args.prompt_file) if args.prompt_file else args.prompt
    answer = args.text if args.text is not None else read_text(args.answer_file)
    result = MultiAgentPromptManager(max_rounds=args.max_rounds, stop_risk_score=args.stop_risk_score).evaluate(
        prompt,
        answer,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
