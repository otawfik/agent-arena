# Agent Arena

A tiny multi-agent framework where AI agents plan, argue, fact-check, and judge debates, with a live dashboard that streams every agent's reasoning as it happens.

No API keys, no GPU, no paid services. Everything runs locally with Python and Flask.

## What it is

Agent Arena is a from-scratch agent framework built around three ideas:

1. **A shared message bus** (`agent_arena/bus.py`): every agent publishes structured events (thinking traces, messages, tool calls, tool results, scores, verdicts). The bus keeps an ordered history and fans out to subscribers.
2. **Tool-using agents** (`agent_arena/agents.py`, `agent_arena/tools.py`): a Planner frames the motion, two Debaters argue the sides, a Fact-Checker audits claims against a bundled fact corpus, and a Judge scores evidence, rhetoric, and rebuttal to declare a winner.
3. **A live dashboard** (`agent_arena/web.py`): a Flask app that runs debates in the background and streams every event to the browser, with agent activity cards, a live transcript, a scoreboard, and the final verdict.

The signature demo: agents debate **pineapple on pizza**.

## Features

- Complete agent pipeline: planning, opening statements, rebuttals, fact-check interlude, audience poll, closing statements, judging
- Transparent reasoning: every agent narrates its strategy in `thinking` events before acting
- Local tool suite: fact-base lookup, rhetoric analyzer, claim checker, simulated audience poll
- Live web dashboard with agent status cards, streaming transcript, scoreboard, and verdict
- CLI demo with colored terminal output
- 4 built-in debate topics (pineapple pizza, tabs vs spaces, hot dog taxonomy, cereal as soup), easy to extend
- Full test suite covering the bus, tools, agents, debate pipeline, and web API

## Quickstart

```bash
git clone https://github.com/otawfik/agent-arena.git
cd agent-arena
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

**Terminal demo:**

```bash
python demo.py                        # pineapple on pizza, the classic
python demo.py --topic tabs-vs-spaces # the indentation wars
python demo.py --list                 # see all topics
```

**Web dashboard:**

```bash
python app.py
```

Then open http://127.0.0.1:5000, pick a topic, hit **Start Debate**, and watch the agents think out loud.

## How it works

```
Topic -> Planner (frames motion, sets judging criteria)
      -> Pro opens, Con opens          (fact-backed arguments)
      -> Pro rebuts, Con rebuts        (direct engagement with opponent claims)
      -> Veritas fact-checks every claim against the corpus
      -> Audience poll simulates crowd reaction
      -> Pro closes, Con closes
      -> Justice Arena scores and rules
```

The Judge scores each side on a transparent card:

- **Rhetoric (40%)**: evidence markers, rhetorical questions, structure
- **Evidence (weight 1.5x)**: raw count of fact-grounded points
- **Fact record (weight 2x)**: supported claims minus disputed ones
- **Rebuttal engagement**: directly addressing the opponent's points

## Project structure

```
agent-arena/
  agent_arena/
    bus.py          # message bus: ordered events + subscriber fan-out
    tools.py        # local tools: fact base, rhetoric analyzer, claim checker, poll
    agents.py       # Planner, Debater, FactCheckerAgent, Judge
    debate.py       # orchestrator: the 7-stage debate pipeline
    web.py          # Flask app: live dashboard API
    templates/      # dashboard UI
    static/         # dashboard styling
  data/
    topics.json     # debate topics
    facts.json      # curated fact corpus (stance-tagged)
  app.py            # web entrypoint
  demo.py           # CLI entrypoint
  tests/            # pytest suite
```

## Swapping in a real LLM

Every agent has a `respond(prompt)` seam designed for this. To upgrade an agent from scripted reasoning to a live model:

```python
class LLMDebater(Debater):
    def respond(self, prompt: str) -> str:
        # call your model of choice here (OpenAI, Anthropic, Ollama...)
        return llm_client.chat(prompt, system=self.persona)
```

Then have the agent's `opening` / `rebuttal` / `closing` methods build their
prompts from tool results and pass them through `respond()` instead of the
template composer. The bus, tools, orchestrator, and dashboard all keep
working unchanged, because they only depend on the event protocol, not on
how text gets generated.

The tools are swappable the same way: each follows the `Tool` protocol
(`name`, `description`, `run`), so a real web-search or vector-store tool
can replace `FactBase` without touching the agents.

## Tech highlights

- **Event-driven agent architecture**: agents never call each other directly; all coordination flows through the bus, which makes the system observable and the dashboard trivial
- **Heuristic NLP**: rhetoric scoring and claim verification with transparent, testable rules instead of black-box calls
- **Seeded simulation**: the audience poll is deterministic per seed, so debates are reproducible
- **Background task streaming**: Flask runs each debate on a worker thread and serves events via lightweight polling

## Screenshots

Run `python app.py` and open http://127.0.0.1:5000 to see the dashboard:
agent activity cards on the left, the streaming transcript in the center,
and the scoreboard with the final verdict on the right.

## Requirements

- Python 3.10+
- Flask 3.0+ (the only dependency)
