"""CLI demo: run a full debate in the terminal.

Usage:
    python demo.py                        # default: pineapple on pizza
    python demo.py --topic tabs-vs-spaces
    python demo.py --topic hot-dog-sandwich --seed 42
    python demo.py --list                 # show available topics
"""

from __future__ import annotations

import argparse

from agent_arena.bus import MessageBus
from agent_arena.debate import DebateOrchestrator
from agent_arena.tools import FactBase

COLORS = {
    "thinking": "\033[90m",
    "message": "\033[97m",
    "tool_call": "\033[94m",
    "tool_result": "\033[36m",
    "plan": "\033[95m",
    "score": "\033[93m",
    "verdict": "\033[92m",
}
RESET = "\033[0m"
BOLD = "\033[1m"


def print_event(event) -> None:
    color = COLORS.get(event.kind, "")
    if event.kind == "thinking":
        print(f"{color}[{event.agent} thinks] {event.text}{RESET}")
    elif event.kind in ("tool_call", "tool_result"):
        print(f"{color}[{event.kind}] {event.agent}: {event.text}{RESET}")
    elif event.kind == "verdict":
        print(f"\n{color}{BOLD}>>> WINNER: {event.text.upper()}{RESET}\n")
    else:
        header = f"[{event.round}] " if event.round else ""
        print(f"\n{color}{BOLD}{header}{event.agent}:{RESET}{color} {event.text}{RESET}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Arena CLI debate demo")
    parser.add_argument("--topic", default="pineapple-pizza", help="Debate topic id")
    parser.add_argument("--seed", type=int, default=7, help="Random seed")
    parser.add_argument("--list", action="store_true", help="List topics and exit")
    parser.add_argument("--quiet", action="store_true", help="Only show messages and verdict")
    args = parser.parse_args()

    if args.list:
        for topic in FactBase().topics():
            print(f"  {topic}: {FactBase().motion(topic)}")
        return

    bus = MessageBus()
    if not args.quiet:
        bus.subscribe(print_event)
    else:
        bus.subscribe(lambda e: print_event(e) if e.kind in ("message", "verdict") else None)

    orchestrator = DebateOrchestrator(topic=args.topic, seed=args.seed, bus=bus)
    result = orchestrator.run()

    j = result["judgement"]
    print(f"\n{BOLD}=== FINAL SCORECARD ==={RESET}")
    for side in ("pro", "con"):
        s = j["scores"][side]
        print(f"  {side.upper():4s} rhetoric={s['rhetoric']:<6} evidence={s['evidence_hits']:<3} "
              f"facts={s['fact_net']:+d}   total={s['total']}")
    print(f"  Audience: PRO {result['audience']['pro']}% / CON {result['audience']['con']}%")
    print(f"\n{j['verdict']}")


if __name__ == "__main__":
    main()
