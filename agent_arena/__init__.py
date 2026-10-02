"""Agent Arena: a tiny multi-agent framework with a live reasoning dashboard.

Agents communicate over a shared message bus, call local tools, and debate
motions. Everything runs offline with no API keys required. Each agent's
``respond`` method is a clean seam: swap it for a real LLM call to go from
scripted reasoning to live models.
"""

from .bus import Event, MessageBus
from .agents import Agent, Planner, Debater, FactCheckerAgent, Judge
from .debate import DebateOrchestrator, run_debate

__all__ = [
    "Event",
    "MessageBus",
    "Agent",
    "Planner",
    "Debater",
    "FactCheckerAgent",
    "Judge",
    "DebateOrchestrator",
    "run_debate",
]

__version__ = "1.0.0"
