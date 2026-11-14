#!/usr/bin/env python3
"""Validate artifacts and reconstruct evidence from the two execution logs."""
import argparse
import json
import re
from pathlib import Path

from run_agent import ROOT, digest, load


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def evaluate(out, fixture=None):
    task = load(ROOT / "task-contract.json")
    fixture = load(ROOT / task["fixture"]) if fixture is None else fixture
    sources = {source["id"]: source for source in fixture}
    calls, results = jsonl(out / "trajectory.jsonl"), jsonl(out / "tool-results.jsonl")
    rows = []
    for budget in (3, 6):
        run = f"steps-{budget}"
        trace = [row for row in calls if row["run_id"] == run]
        obs = [row for row in results if row["run_id"] == run]
        if not trace or trace[-1].get("event") != "stop":
            raise ValueError(f"{run}: stop event missing")
        actions, stop = trace[:-1], trace[-1]
        if len(actions) != len(obs) or not (len(actions) == stop["steps_used"] <= budget):
            raise ValueError(f"{run}: inconsistent step count")
        searched = set()
        read = {}
        saved = None
        artifact = out / run / task["output"]
        body = artifact.read_text(encoding="utf-8") if artifact.is_file() else ""
        for step, (action, observation) in enumerate(zip(actions, obs), 1):
            name, args, result = action["tool"], action["arguments"], observation["result"]
            if any(entry["step"] != step or entry["call_id"] != f"{run}:{step}"
                   or entry["tool"] != name for entry in (action, observation)):
                raise ValueError(f"{run}: call/observation mismatch at step {step}")
            if not result["ok"]:
                continue
            if name == "search_sources" and step == 1 and args == {"terms": task["query"]}:
                expected = [dict(id=s["id"], title=s["title"], topic=s["topic"])
                            for s in sources.values() if set(task["query"]) <= set(s["tags"])]
                if result.get("hits") == expected:
                    searched = {hit["id"] for hit in expected}
            elif name == "read_source":
                sid = args.get("source_id")
                if sid in searched and result.get("source") == sources[sid]:
                    read[sid] = sources[sid]
            elif name == "write_brief" and len(read) == task["required_sources"]:
                if (step == len(actions) and stop["reason"] == "submitted" and body
                        and body == args.get("markdown") and result.get("artifact") == artifact.name
                        and result.get("sha256") == digest(artifact)):
                    saved = body
        enough = len(read) == task["required_sources"] and {
            source["topic"] for source in read.values()
        } == set(task["topics"])
        bullets = [line for line in (saved or "").splitlines() if line.startswith("- ")]
        pattern = re.compile(r"- \*\*(.+?)\*\*\s+(.+?) \[([^ ]+) · (.+?) · (.+?)\]\(([^)]+)\)")
        cited = set()
        for line in bullets:
            match = pattern.fullmatch(line)
            if not match:
                continue
            topic, claim, sid, title, locator, url = match.groups()
            source = read.get(sid)
            if source and (topic, claim, title, locator, url) == tuple(
                    source[key] for key in ("topic", "claim", "title", "locator", "url")):
                cited.add(sid)
        checks = {
            "search_complete": bool(searched),
            "three_relevant_reads": enough,
            "brief_written": bool(saved),
            "citation_evidence": enough and cited == set(read) and len(bullets) == len(cited),
            "one_page_scope": bool(saved) and len(saved) <= task["max_chars"]
                              and len(bullets) == task["required_sources"]
                              and saved.count("## 对实验设计的启示\n\n") == 1
                              and bool(saved.partition("## 对实验设计的启示\n\n")[2].strip()),
        }
        rows.append(dict(run_id=run, max_steps=budget, tool_calls=len(obs),
                         unique_relevant_reads=len(read), citation_count=len(cited),
                         stop_reason=stop["reason"],
                         **{key: int(value) for key, value in checks.items()},
                         checks_passed=sum(checks.values()),
                         status="PASS" if all(checks.values()) else "FAIL"))
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT)
    args = parser.parse_args()
    rows = evaluate(args.out)
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    root_brief = args.out / "final-brief.md"
    verified_brief = args.out / "steps-6/final-brief.md"
    ok = rows[1]["status"] == "PASS" and root_brief.is_file() and (
        root_brief.read_bytes() == verified_brief.read_bytes()
    )
    raise SystemExit(0 if ok else 1)
