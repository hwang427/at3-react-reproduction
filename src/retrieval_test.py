"""Paired one-tag perturbations with a fixed six-call budget."""
import argparse
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from run_agent import ROOT, load, run, write_jsonl
from validate import evaluate

ALIASES = {"评测": "评估", "评价": "评估", "测评": "评估"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    out = parser.parse_args().out
    out.mkdir(parents=True, exist_ok=True)
    task = load(ROOT / "task-contract.json")
    schema = load(ROOT / "tool-schema.json")
    base = load(ROOT / task["fixture"])
    rows, traces = [], []
    for sid in ("S01", "S02", "S03"):
        for alias in ALIASES:
            variant = [{**item, "tags": [alias if item["id"] == sid and tag == "评估" else tag
                                        for tag in item["tags"]]} for item in base]
            for mode in ("exact", "canonical"):
                sources = variant if mode == "exact" else [
                    {**item, "tags": [ALIASES.get(tag, tag) for tag in item["tags"]]}
                    for item in variant
                ]
                with TemporaryDirectory() as directory:
                    target = Path(directory)
                    short_calls, short_obs = run(3, task, schema, sources, target)
                    calls, obs = run(6, task, schema, sources, target)
                    write_jsonl(target / "trajectory.jsonl", short_calls + calls)
                    write_jsonl(target / "tool-results.jsonl", short_obs + obs)
                    status = evaluate(target, fixture=sources)[1]["status"]
                    row = dict(source=sid, alias=alias, mode=mode, status=status,
                               calls=len(obs), reads=sum("source" in x["result"] for x in obs),
                               stop=calls[-1]["reason"])
                    rows.append(row)
                    traces.append(dict(row, trajectory=calls, observations=obs))
    with (out / "retrieval-evaluation.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write_jsonl(out / "retrieval-trajectory.jsonl", traces)
    for mode in ("exact", "canonical"):
        group = [r for r in rows if r["mode"] == mode]
        print(mode, sum(r["status"] == "PASS" for r in group), "/", len(group))


if __name__ == "__main__":
    main()
