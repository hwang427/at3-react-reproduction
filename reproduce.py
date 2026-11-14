#!/usr/bin/env python3
"""Offline, deterministic reconstruction of ReAct's action loop."""
import argparse
import csv
import json
import re
import unicodedata
from pathlib import Path


class Wiki:
    def __init__(self, pages):
        self.pages = pages
        self.current = None
        self.answer = None

    def step(self, action, argument):
        if action == "Search":
            self.current = self.pages.get(argument)
            return self.current[0] if self.current else "未找到页面"
        if action == "Lookup":
            return next((line for line in self.current or [] if argument in line), "未找到字段")
        if action == "Finish":
            self.answer = argument
            return "已提交"
        raise ValueError(action)


def field(text, name):
    match = re.search(rf"{name}=([^。\n]+)", text)
    return match[1] if match else None


def run(project, pages, mode, budget=5):
    wiki = Wiki(pages)
    action, argument = "Search", project
    thought = "先查项目，找到负责机构。"
    events = []
    for step in range(1, budget + 1):
        observation = wiki.step(action, argument)
        event = dict(step=step, action=action, argument=argument, observation=observation)
        if mode == "react":
            event["thought"] = thought
        events.append(event)
        if action == "Finish":
            break
        if action == "Search" and argument == project:
            action, argument = "Search", field(observation, "负责机构")
            thought = "已找到负责机构，查询其页面。"
            continue
        district = field(observation, "所在区")
        if district:
            action, argument = "Finish", district
            thought = "观察已给出所在区，提交答案。"
        elif mode == "react" and action == "Search":
            action, argument = "Lookup", "所在区"
            thought = "页面摘要缺少所在区，在当前页面内查找字段。"
        else:
            action, argument = "Finish", "未知"
            thought = "没有可用的所在区证据。"
    return wiki.answer, events


def normalized(value):
    return "".join(unicodedata.normalize("NFKC", value or "").casefold().split())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "results")
    out = parser.parse_args().out
    out.mkdir(parents=True, exist_ok=True)
    cases = json.loads(Path(__file__).with_name("cases.json").read_text(encoding="utf-8"))
    pages = {}
    for project, org, district, placement in cases:
        pages[project] = [f"负责机构={org}。"]
        pages[org] = (
            [f"所在区={district}。", "设有数据档案室。"]
            if placement == "lead"
            else ["设有数据档案室。", f"所在区={district}。"]
        )
    rows = []
    with (out / "trajectory.jsonl").open("w", encoding="utf-8") as trace:
        for project, _, expected, placement in cases:
            for mode in ("act", "react"):
                answer, events = run(project, pages, mode)
                exact = int(normalized(answer) == normalized(expected))
                rows.append(dict(case=project, placement=placement, mode=mode,
                                 answer=answer, expected=expected, exact_match=exact,
                                 tool_calls=len(events)))
                trace.write(json.dumps(dict(case=project, mode=mode, events=events),
                                       ensure_ascii=False) + "\n")
    with (out / "evaluation.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = ["AT3 / 02  ReAct offline reproduction", f"Cases: {len(cases)} | Tool budget per run: 5",
             "", "Policy       Exact match        Lead       Body       Calls"]
    for mode in ("act", "react"):
        selected = [row for row in rows if row["mode"] == mode]
        n = len(selected)
        hits = sum(row["exact_match"] for row in selected)
        lead = [row for row in selected if row["placement"] == "lead"]
        body = [row for row in selected if row["placement"] == "body"]
        calls = sum(row["tool_calls"] for row in selected)
        lines.append(f"{mode:<12} {hits:>2}/{n} ({hits/n:>6.1%})"
                     f"         {sum(r['exact_match'] for r in lead)}/{len(lead)}"
                     f"        {sum(r['exact_match'] for r in body)}/{len(body)}"
                     f"        {calls}")
    lines += ["", "Paper Table 1 (HotpotQA EM): Act 25.7% | ReAct 27.4%",
              "Local: synthetic data and rule policies; scores are not comparable.",
              "", "Wrote evaluation.csv and trajectory.jsonl."]
    summary = "\n".join(lines) + "\n"
    (out / "summary.txt").write_text(summary, encoding="utf-8")
    print(summary, end="")


if __name__ == "__main__":
    main()
