"""Message bus: the shared nervous system of the arena.

Every agent publishes structured events (thinking traces, messages, tool
calls, tool results, scores, verdicts) to the bus. The bus keeps an ordered
history and notifies subscribers, which is what lets the web dashboard show
live reasoning as a debate unfolds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Optional


@dataclass
class Event:
    seq: int
    kind: str  # thinking | message | tool_call | tool_result | plan | score | verdict
    agent: str
    text: str
    round: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return {
            "seq": self.seq,
            "kind": self.kind,
            "agent": self.agent,
            "text": self.text,
            "round": self.round,
            "timestamp": self.timestamp,
        }


class MessageBus:
    """Ordered, in-memory event bus with subscriber fan-out."""

    def __init__(self) -> None:
        self._events: List[Event] = []
        self._subscribers: List[Callable[[Event], None]] = []
        self._seq = 0

    def publish(self, kind: str, agent: str, text: str, round: str = "") -> Event:
        self._seq += 1
        event = Event(seq=self._seq, kind=kind, agent=agent, text=text, round=round)
        self._events.append(event)
        for subscriber in list(self._subscribers):
            subscriber(event)
        return event

    def subscribe(self, fn: Callable[[Event], None]) -> None:
        self._subscribers.append(fn)

    def unsubscribe(self, fn: Callable[[Event], None]) -> None:
        if fn in self._subscribers:
            self._subscribers.remove(fn)

    def history(self, kind: Optional[str] = None, agent: Optional[str] = None) -> List[Event]:
        events = self._events
        if kind is not None:
            events = [e for e in events if e.kind == kind]
        if agent is not None:
            events = [e for e in events if e.agent == agent]
        return list(events)

    def __len__(self) -> int:
        return len(self._events)
