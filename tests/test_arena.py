"""Tests for the Agent Arena framework."""

import json

import pytest

from agent_arena import (
    DebateOrchestrator,
    FactCheckerAgent,
    Judge,
    MessageBus,
    Planner,
    run_debate,
)
from agent_arena.tools import AudiencePoll, ClaimChecker, FactBase, RhetoricAnalyzer
from agent_arena.web import create_app


def test_bus_publish_and_history():
    bus = MessageBus()
    seen = []
    bus.subscribe(seen.append)
    bus.publish("thinking", "Pro", "hmm", round="R1")
    bus.publish("message", "Con", "nope", round="R1")
    assert len(bus) == 2
    assert [e.kind for e in bus.history()] == ["thinking", "message"]
    assert bus.history(kind="message")[0].agent == "Con"
    assert seen[0].seq == 1 and seen[1].seq == 2
    assert bus.history(agent="Nobody") == []


def test_fact_base_lookup():
    fb = FactBase()
    assert "pineapple-pizza" in fb.topics()
    assert "pineapple" in fb.motion("pineapple-pizza").lower()
    pro = fb.run("pineapple-pizza", stance="pro", limit=2)
    assert pro["count"] >= 2 and len(pro["facts"]) == 2
    assert all(f["stance"] == "pro" for f in pro["facts"])
    kw = fb.run("pineapple-pizza", keywords="1962 invented Ontario")
    assert kw["facts"] and "1962" in kw["facts"][0]["text"]


def test_rhetoric_analyzer_scores_evidence():
    analyzer = RhetoricAnalyzer()
    rich = ("Consider this: studies show the effect is real. For example, according to "
            "the record, history shows three clear cases. Isn't that compelling?")
    plain = "I think this is fine and good."
    assert analyzer.run(rich)["score"] > analyzer.run(plain)["score"]
    assert analyzer.run(rich)["evidence_hits"] >= 3


def test_claim_checker_verdicts():
    fb = FactBase()
    checker = ClaimChecker(fb)
    supported = checker.run("Hawaiian pizza was invented in 1962 by Sam Panopoulos in Ontario", "pineapple-pizza")
    assert supported["verdict"] == "supported"
    assert supported["matched_fact"] is not None
    unknown = checker.run("zzz qqq waffles orbit the moon nightly", "pineapple-pizza")
    assert unknown["verdict"] == "unverifiable"


def test_audience_poll_bounded():
    poll = AudiencePoll(seed=1)
    result = poll.run("A very persuasive argument with lots of evidence.", 50.0)
    assert 5.0 <= result["new_support"] <= 95.0
    assert result["sample"] == 100


def test_planner_frames_motion():
    bus = MessageBus()
    planner = Planner("Vera", "moderator", "fair", bus, {}, seed=1)
    plan = planner.plan("pineapple-pizza", "Motion text here.")
    assert plan["motion"] == "Motion text here."
    assert len(plan["criteria"]) == 3
    assert any(e.kind == "plan" for e in bus.history())


def test_full_debate_end_to_end():
    result = run_debate("pineapple-pizza", seed=7)
    assert result["motion"]
    assert len(result["transcript"]) == 6  # 2 openings + 2 rebuttals + 2 closings
    rounds = {t["round"] for t in result["transcript"]}
    assert rounds == {"Opening Statements", "Rebuttals", "Closing Statements"}
    assert result["judgement"]["winner"] in ("pro", "con")
    assert result["fact_results"], "fact-check interlude must produce results"
    assert 0 < result["audience"]["pro"] < 100


def test_debate_events_cover_pipeline():
    bus = MessageBus()
    DebateOrchestrator(topic="tabs-vs-spaces", seed=3, bus=bus).run()
    kinds = {e.kind for e in bus.history()}
    assert {"thinking", "message", "tool_call", "tool_result", "plan", "score", "verdict"} <= kinds
    assert bus.history(kind="verdict")[0].text in ("pro", "con")


def test_unknown_topic_rejected():
    with pytest.raises(ValueError):
        DebateOrchestrator(topic="not-a-topic")


def test_web_api_flow():
    app = create_app()
    client = app.test_client()
    assert client.get("/").status_code == 200
    topics = client.get("/api/topics").get_json()
    assert any(t["id"] == "pineapple-pizza" for t in topics)
    started = client.post("/api/start", json={"topic": "cereal-soup"}).get_json()
    run_id = started["run_id"]
    events, done = [], False
    for _ in range(200):
        payload = client.get(f"/api/events?run_id={run_id}&since={len(events)}").get_json()
        events.extend(payload["events"])
        if payload["done"]:
            done = True
            break
    assert done and events, "debate should stream events then finish"
    result = client.get(f"/api/result?run_id={run_id}").get_json()
    assert result["done"] and result["result"]["judgement"]["winner"] in ("pro", "con")
    bad = client.post("/api/start", json={"topic": "nope"})
    assert bad.status_code == 400


def test_topics_json_matches_fact_corpus():
    from pathlib import Path
    data_dir = Path(__file__).resolve().parent.parent / "data"
    topics = {t["id"] for t in json.loads((data_dir / "topics.json").read_text())["topics"]}
    facts = set(json.loads((data_dir / "facts.json").read_text()))
    assert topics == facts
