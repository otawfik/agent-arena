"""Agent personas: planner, debaters, fact-checker, and judge.

Each agent is deliberately transparent: before acting it publishes a
``thinking`` event describing its plan, then publishes its ``message`` and
any ``tool_call`` / ``tool_result`` events. That trace is exactly what the
dashboard streams.

The reasoning here is heuristic and offline. To plug in a real model,
override ``respond`` on any agent (see README: "Swapping in a real LLM").
"""

from __future__ import annotations

import random
from typing import Any, Dict, List

from .bus import MessageBus
from .tools import Tool

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "were",
    "been", "their", "they", "them", "then", "than", "into", "over",
    "such", "will", "would", "what", "when", "which", "while", "your",
}


class Agent:
    """Base agent: a named role with tools and a bus to think out loud on."""

    def __init__(self, name: str, role: str, persona: str,
                 bus: MessageBus, tools: Dict[str, Tool], seed: int = 0) -> None:
        self.name = name
        self.role = role
        self.persona = persona
        self.bus = bus
        self.tools = tools
        self.rng = random.Random(seed or abs(hash(name)) % (2 ** 31))

    # -- bus helpers -----------------------------------------------------
    def think(self, text: str, round: str = "") -> None:
        self.bus.publish("thinking", self.name, text, round)

    def say(self, text: str, round: str = "") -> str:
        self.bus.publish("message", self.name, text, round)
        return text

    def use_tool(self, tool_name: str, round: str = "", **kwargs: Any) -> Dict[str, Any]:
        arg_summary = ", ".join(f"{k}={str(v)[:40]}" for k, v in kwargs.items())
        self.bus.publish("tool_call", self.name, f"{tool_name}({arg_summary})", round)
        result = self.tools[tool_name].run(**kwargs)
        preview = str(result)[:220]
        self.bus.publish("tool_result", self.name, f"{tool_name} returned: {preview}", round)
        return result

    def respond(self, prompt: str) -> str:  # LLM seam
        """Generate a response. Override this to call a real LLM."""
        raise NotImplementedError("Override respond() or use a scripted agent.")


class Planner(Agent):
    """Frames the motion, sets the judging criteria, assigns sides."""

    def plan(self, topic: str, motion: str) -> Dict[str, Any]:
        self.think(
            f"New debate requested on topic '{topic}'. I need to frame a fair "
            f"motion, define what 'winning' means, and assign the debaters "
            f"their sides so neither starts with an advantage.",
            round="Planning",
        )
        criteria = [
            "Evidence: claims grounded in verifiable facts score highest.",
            "Rhetoric: clarity, structure, and persuasive devices matter.",
            "Rebuttal: directly engaging the opponent's points beats ignoring them.",
        ]
        for line in criteria:
            self.bus.publish("plan", self.name, line, round="Planning")
        brief = (
            f"Today's motion: {motion} "
            f"Pro will defend the motion; Con will oppose it. "
            f"We will hear opening statements, one round of rebuttals, "
            f"a fact-check interlude, and closing statements. May the best reasoning win."
        )
        self.say(brief, round="Planning")
        return {"motion": motion, "criteria": criteria}


class Debater(Agent):
    """Argues one side of the motion using facts plus rhetorical craft."""

    OPENERS = [
        "Let's start with the facts, because the facts are on my side.",
        "My opponent will dress this up, but the record is clear.",
        "Consider the evidence with an open mind.",
    ]
    REBUTTAL_LEADS = [
        "My opponent claims {claim}. That misses the point entirely:",
        "Let's examine what was just said: {claim}. Here's the problem with that:",
        "A clever line, but {claim} falls apart under scrutiny:",
    ]
    CLOSERS = [
        "The evidence is in, the logic holds, and the conclusion is unavoidable.",
        "When the noise fades, what remains is the truth of my case.",
        "I rest my case knowing reason is on my side.",
    ]

    def __init__(self, *args: Any, stance: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.stance = stance  # "pro" or "con"
        self.claims: List[str] = []

    def _fact_sentence(self, fact: Dict[str, Any]) -> str:
        frames = [
            f"Consider this: {fact['text']}",
            f"For example, {fact['text'][0].lower() + fact['text'][1:]}",
            f"History shows that {fact['text'][0].lower() + fact['text'][1:]}",
            f"According to the record, {fact['text'][0].lower() + fact['text'][1:]}",
        ]
        return self.rng.choice(frames)

    def opening(self, topic: str) -> str:
        self.think(
            f"I am arguing {self.stance.upper()}. Strategy: pull the strongest "
            f"{self.stance} facts from the corpus, lead with my best evidence, "
            f"and frame each fact as an argument, not just a statement.",
            round="Opening Statements",
        )
        facts = self.use_tool("fact_base", topic=topic, stance=self.stance,
                              limit=3, round="Opening Statements")["facts"]
        parts = [self.rng.choice(self.OPENERS)]
        for i, fact in enumerate(facts, 1):
            sentence = self._fact_sentence(fact)
            parts.append(f"My {'first' if i == 1 else 'second' if i == 2 else 'third'} point: {sentence}")
            self.claims.append(fact["text"])
        parts.append("The pattern is undeniable, and my case is built on evidence, not vibes.")
        return self.say(" ".join(parts), round="Opening Statements")

    def rebuttal(self, topic: str, opponent_claims: List[str]) -> str:
        self.think(
            f"Rebuttal time. I will take my opponent's claims one by one, "
            f"find counter-evidence in the fact base, and turn their points "
            f"against them. Direct engagement scores with the judge.",
            round="Rebuttals",
        )
        facts = self.use_tool("fact_base", topic=topic, stance=self.stance,
                              limit=6, round="Rebuttals")["facts"]
        parts = []
        for claim, fact in zip(opponent_claims[:2], facts):
            short = claim.split(".")[0][:90]
            lead = self.rng.choice(self.REBUTTAL_LEADS).format(claim=f'"{short}..."')
            parts.append(f"{lead} {self._fact_sentence(fact)}")
            self.claims.append(fact["text"])
        if not parts:
            parts.append("My opponent offered assertions without substance, and the facts remain mine.")
        return self.say(" ".join(parts), round="Rebuttals")

    def closing(self, topic: str) -> str:
        self.think(
            "Closing statement. No new evidence needed: I will restate my "
            "strongest point, remind the judge of my opponent's weakest moment, "
            "and end with a memorable line.",
            round="Closing Statements",
        )
        facts = self.use_tool("fact_base", topic=topic, stance=self.stance,
                              limit=1, round="Closing Statements")["facts"]
        anchor = facts[0]["text"] if facts else "the weight of the evidence"
        text = (
            f"If you remember one thing from this debate, remember this: {anchor} "
            f"{self.rng.choice(self.CLOSERS)}"
        )
        return self.say(text, round="Closing Statements")


class FactCheckerAgent(Agent):
    """Audits every claim made in the debate against the fact corpus."""

    def audit(self, topic: str, claims: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        self.think(
            f"Auditing {len(claims)} claims from both sides against the fact "
            f"corpus. Supported claims boost a side; disputed ones hurt it; "
            f"unverifiable ones are noted but not punished.",
            round="Fact Check",
        )
        results = []
        for claim in claims:
            verdict = self.use_tool("claim_checker", claim=claim["text"],
                                    topic=topic, round="Fact Check")
            results.append({"claim": claim["text"], "side": claim["side"], **verdict})
            mark = {"supported": "SUPPORTED", "disputed": "DISPUTED",
                    "unverifiable": "UNVERIFIABLE"}[verdict["verdict"]]
            self.bus.publish(
                "score", self.name,
                f"[{mark}] ({claim['side']}) {claim['text'][:110]}",
                round="Fact Check",
            )
        supported = sum(1 for r in results if r["verdict"] == "supported")
        disputed = sum(1 for r in results if r["verdict"] == "disputed")
        self.say(
            f"Audit complete: {supported} claims supported, {disputed} disputed, "
            f"{len(results) - supported - disputed} unverifiable. The judge has the record.",
            round="Fact Check",
        )
        return results


class Judge(Agent):
    """Scores both sides on evidence, rhetoric, and rebuttal, then rules."""

    def deliberate(self, topic: str, pro_texts: List[str], con_texts: List[str],
                   fact_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        self.think(
            "Deliberation. I will score each side's full body of argument with "
            "the rhetoric analyzer, tally the fact-check record, and reward "
            "the side that engaged its opponent most directly.",
            round="Judging",
        )
        analyzer = self.tools["rhetoric_analyzer"]
        scores = {}
        for side, texts in (("pro", pro_texts), ("con", con_texts)):
            analyses = [analyzer.run(t) for t in texts]
            rhetoric = sum(a["score"] for a in analyses) / max(len(analyses), 1)
            evidence = sum(a["evidence_hits"] for a in analyses)
            side_facts = [r for r in fact_results if r["side"] == side]
            fact_net = (
                sum(1 for r in side_facts if r["verdict"] == "supported")
                - sum(1 for r in side_facts if r["verdict"] == "disputed")
            )
            rebuttal_hits = sum(t.lower().count("my opponent") for t in texts)
            total = round(rhetoric * 0.4 + evidence * 1.5 + fact_net * 2.0 + rebuttal_hits * 1.0, 2)
            scores[side] = {
                "rhetoric": round(rhetoric, 2),
                "evidence_hits": evidence,
                "fact_net": fact_net,
                "rebuttal_engagement": rebuttal_hits,
                "total": total,
            }
            self.bus.publish(
                "score", self.name,
                f"{side.upper()} card: rhetoric {rhetoric:.2f}, evidence hits {evidence}, "
                f"fact record {fact_net:+d}, rebuttal engagement {rebuttal_hits} "
                f"=> total {total:.2f}",
                round="Judging",
            )
        winner = "pro" if scores["pro"]["total"] >= scores["con"]["total"] else "con"
        margin = round(abs(scores["pro"]["total"] - scores["con"]["total"]), 2)
        verdict = (
            f"After weighing evidence, rhetoric, and rebuttal, I rule for the "
            f"{winner.upper()} side by a margin of {margin:.2f} points. "
            f"{'The facts carried the day.' if scores[winner]['fact_net'] >= 0 else 'Style overcame a thin factual record.'}"
        )
        self.say(verdict, round="Verdict")
        self.bus.publish("verdict", self.name, winner, round="Verdict")
        return {"scores": scores, "winner": winner, "margin": margin, "verdict": verdict}
