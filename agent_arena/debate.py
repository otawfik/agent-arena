"""Debate orchestrator: runs the full multi-agent debate pipeline.

Pipeline: Planner frames the motion -> opening statements -> rebuttals ->
fact-check interlude -> closing statements -> audience poll -> judging.
Every step publishes to the message bus, so any subscriber (CLI printer,
web dashboard) sees the debate live.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .agents import Debater, FactCheckerAgent, Judge, Planner
from .bus import MessageBus
from .tools import FactBase, default_tools

PERSONAS = {
    "planner": (
        "Vera the Moderator",
        "moderator",
        "A fair, crisp moderator who frames motions and keeps debates honest.",
    ),
    "pro": (
        "Pro",
        "debater",
        "A passionate advocate who argues FOR the motion with evidence and flair.",
    ),
    "con": (
        "Con",
        "debater",
        "A sharp skeptic who argues AGAINST the motion and dismantles weak claims.",
    ),
    "fact_checker": (
        "Veritas the Fact-Checker",
        "fact-checker",
        "A meticulous auditor who verifies every claim against the record.",
    ),
    "judge": (
        "Justice Arena",
        "judge",
        "An impartial judge who scores evidence, rhetoric, and rebuttal.",
    ),
}


class DebateOrchestrator:
    def __init__(self, topic: str = "pineapple-pizza", seed: int = 7,
                 bus: MessageBus | None = None) -> None:
        self.topic = topic
        self.bus = bus if bus is not None else MessageBus()
        self.fact_base = FactBase()
        if topic not in self.fact_base.topics():
            raise ValueError(
                f"Unknown topic '{topic}'. Available: {self.fact_base.topics()}"
            )
        self.tools = default_tools(self.fact_base)
        self.motion = self.fact_base.motion(topic)
        self.planner = Planner(*PERSONAS["planner"], bus=self.bus, tools=self.tools, seed=seed)
        self.pro = Debater(*PERSONAS["pro"], bus=self.bus, tools=self.tools, seed=seed + 1, stance="pro")
        self.con = Debater(*PERSONAS["con"], bus=self.bus, tools=self.tools, seed=seed + 2, stance="con")
        self.fact_checker = FactCheckerAgent(*PERSONAS["fact_checker"], bus=self.bus,
                                             tools=self.tools, seed=seed + 3)
        self.judge = Judge(*PERSONAS["judge"], bus=self.bus, tools=self.tools, seed=seed + 4)
        self.claims: List[Dict[str, str]] = []
        self.transcript: List[Dict[str, str]] = []

    def _record(self, side: str, text: str, round: str) -> None:
        self.transcript.append({"side": side, "round": round, "text": text})

    def run(self) -> Dict[str, Any]:
        # 1. Planning
        plan = self.planner.plan(self.topic, self.motion)

        # 2. Opening statements
        pro_open = self.pro.opening(self.topic)
        con_open = self.con.opening(self.topic)
        self._record("pro", pro_open, "Opening Statements")
        self._record("con", con_open, "Opening Statements")

        # 3. Rebuttals
        pro_reb = self.pro.rebuttal(self.topic, self.con.claims)
        con_reb = self.con.rebuttal(self.topic, self.pro.claims)
        self._record("pro", pro_reb, "Rebuttals")
        self._record("con", con_reb, "Rebuttals")

        # 4. Fact-check interlude
        self.claims = [{"text": c, "side": "pro"} for c in self.pro.claims] + [
            {"text": c, "side": "con"} for c in self.con.claims
        ]
        fact_results = self.fact_checker.audit(self.topic, self.claims)

        # 5. Closing statements
        pro_close = self.pro.closing(self.topic)
        con_close = self.con.closing(self.topic)
        self._record("pro", pro_close, "Closing Statements")
        self._record("con", con_close, "Closing Statements")

        # 6. Audience pulse
        poll = self.tools["audience_poll"]
        pro_support, con_support = 50.0, 50.0
        for text in (pro_open, pro_reb, pro_close):
            pro_support = poll.run(text, pro_support)["new_support"]
        for text in (con_open, con_reb, con_close):
            con_support = poll.run(text, con_support)["new_support"]
        self.bus.publish(
            "score", "Audience",
            f"Final audience support: PRO {pro_support:.1f}% vs CON {con_support:.1f}%",
            round="Audience Poll",
        )

        # 7. Judging
        pro_texts = [t["text"] for t in self.transcript if t["side"] == "pro"]
        con_texts = [t["text"] for t in self.transcript if t["side"] == "con"]
        judgement = self.judge.deliberate(self.topic, pro_texts, con_texts, fact_results)

        return {
            "topic": self.topic,
            "motion": self.motion,
            "plan": plan,
            "transcript": self.transcript,
            "fact_results": fact_results,
            "audience": {"pro": pro_support, "con": con_support},
            "judgement": judgement,
        }


def run_debate(topic: str = "pineapple-pizza", seed: int = 7) -> Dict[str, Any]:
    """Convenience entry point: run a full debate and return the results."""
    return DebateOrchestrator(topic=topic, seed=seed).run()
