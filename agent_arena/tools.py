"""Local tools the agents can call.

Everything here runs offline against a bundled fact corpus, so the arena
works with no API keys. Each tool follows the same small protocol
(``name``, ``description``, ``run``), which makes it trivial to register new
ones, including wrappers around real APIs or an LLM.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any, Dict, List

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class Tool:
    name = "base_tool"
    description = "Base tool."

    def run(self, **kwargs: Any) -> Dict[str, Any]:  # pragma: no cover
        raise NotImplementedError


class FactBase(Tool):
    """Lookup facts from the bundled debate corpus."""

    name = "fact_base"
    description = "Look up curated facts for a debate topic, optionally filtered by stance."

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DATA_DIR / "facts.json"
        with open(self.path, encoding="utf-8") as fh:
            self._topics: Dict[str, Any] = json.load(fh)

    def topics(self) -> List[str]:
        return list(self._topics.keys())

    def motion(self, topic: str) -> str:
        return self._topics[topic]["motion"]

    def run(self, topic: str, stance: str | None = None, limit: int = 5,
            keywords: str | None = None) -> Dict[str, Any]:
        facts = self._topics[topic]["facts"]
        if stance:
            facts = [f for f in facts if f["stance"] == stance]
        if keywords:
            words = {w.lower() for w in re.findall(r"[a-zA-Z']+", keywords) if len(w) > 3}
            scored = []
            for fact in facts:
                fact_words = {w.lower() for w in re.findall(r"[a-zA-Z']+", fact["text"])}
                overlap = len(words & fact_words)
                if overlap:
                    scored.append((overlap, fact))
            scored.sort(key=lambda pair: pair[0], reverse=True)
            facts = [fact for _, fact in scored]
        return {"facts": facts[:limit], "count": len(facts)}


class RhetoricAnalyzer(Tool):
    """Score an argument's rhetorical quality with transparent heuristics."""

    name = "rhetoric_analyzer"
    description = "Score argument quality: evidence markers, rhetorical devices, structure."

    EVIDENCE_MARKERS = [
        "for example", "for instance", "studies show", "research shows",
        "according to", "data shows", "history shows", "consider",
    ]
    SUPERLATIVES = [
        "best", "worst", "greatest", "most", "undeniable", "clearly",
        "obviously", "unquestionably", "revolutionary",
    ]

    def run(self, text: str) -> Dict[str, Any]:
        lowered = text.lower()
        words = re.findall(r"[a-zA-Z']+", text)
        sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
        evidence_hits = sum(1 for m in self.EVIDENCE_MARKERS if m in lowered)
        questions = text.count("?")
        superlatives = sum(1 for s in self.SUPERLATIVES if re.search(rf"\b{s}\b", lowered))
        triads = len(re.findall(r"\b\w+,\s\w+,\s(?:and\s)?\w+", text))
        structure = min(len(sentences) / 6.0, 1.0)
        score = round(
            min(10.0, evidence_hits * 1.6 + questions * 0.8 + superlatives * 0.5
                + triads * 1.2 + structure * 2.0),
            2,
        )
        return {
            "word_count": len(words),
            "sentence_count": len(sentences),
            "evidence_hits": evidence_hits,
            "rhetorical_questions": questions,
            "superlatives": superlatives,
            "triads": triads,
            "score": score,
        }


class AudiencePoll(Tool):
    """Simulate audience reaction to an argument (seeded, reproducible)."""

    name = "audience_poll"
    description = "Simulate how a 100-person audience shifts after hearing an argument."

    def __init__(self, seed: int = 7) -> None:
        self._rng = random.Random(seed)

    def run(self, text: str, current_support: float = 50.0) -> Dict[str, Any]:
        analysis = RhetoricAnalyzer().run(text)
        quality = analysis["score"] / 10.0
        swing = (quality - 0.45) * 14.0 + self._rng.uniform(-2.0, 2.0)
        new_support = round(max(5.0, min(95.0, current_support + swing)), 1)
        return {
            "previous_support": round(current_support, 1),
            "new_support": new_support,
            "swing": round(new_support - current_support, 1),
            "sample": 100,
        }


class ClaimChecker(Tool):
    """Check a claim against the fact corpus via keyword overlap."""

    name = "claim_checker"
    description = "Verify a debate claim against the curated fact corpus."

    def __init__(self, fact_base: FactBase) -> None:
        self.facts = fact_base

    def run(self, claim: str, topic: str) -> Dict[str, Any]:
        corpus = self.facts.run(topic, limit=50)["facts"]
        claim_words = {w.lower() for w in re.findall(r"[a-zA-Z']+", claim) if len(w) > 3}
        best, best_overlap = None, 0
        for fact in corpus:
            fact_words = {w.lower() for w in re.findall(r"[a-zA-Z']+", fact["text"])}
            overlap = len(claim_words & fact_words)
            if overlap > best_overlap:
                best, best_overlap = fact, overlap
        if best is None or best_overlap < 2:
            return {"verdict": "unverifiable", "matched_fact": None, "overlap": best_overlap}
        verdict = "supported" if best["stance"] != "disputed" else "disputed"
        return {"verdict": verdict, "matched_fact": best["text"], "overlap": best_overlap}


def default_tools(fact_base: FactBase | None = None) -> Dict[str, Tool]:
    fb = fact_base or FactBase()
    return {
        "fact_base": fb,
        "rhetoric_analyzer": RhetoricAnalyzer(),
        "audience_poll": AudiencePoll(),
        "claim_checker": ClaimChecker(fb),
    }
