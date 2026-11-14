#!/usr/bin/env python3
"""Run a deterministic offline tool agent and its budget comparison."""
import argparse
import csv
import hashlib
import json
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUTS = ("task-contract.json", "tool-schema.json", "sources.json",
          "run_agent.py", "validate.py")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_jsonl(path, records):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records),
                    encoding="utf-8")


def source_line(source):
    return (f"- **{source['topic']}**　{source['claim']} "
            f"[{source['id']} · {source['title']} · {source['locator']}]({source['url']})")


def compose(sources):
    lines = ["# 如何评估能调用工具的 Agent", "",
             "同一个 Agent 的工具调用可以看起来合理，但是否完成任务仍需检查外部结果。"
             "下面三个维度分别对应行动过程、任务终态和跨次可靠性。", ""]
    lines.extend(source_line(source) for source in sources)
    lines += ["", "## 对实验设计的启示", "",
              "先记录可复查的工具与观察，再用独立检查器判定产物。若涉及随机模型，"
              "再对同一任务重复运行，报告多次均成功的比例。上述三篇研究的任务和指标各异，"
              "百分比仅用于说明各自的结果。", ""]
    return "\n".join(lines)


class Tools:
    def __init__(self, sources, contract, schema, folder):
        self.sources = {source["id"]: source for source in sources}
        self.contract = contract
        self.schema = schema
        self.folder = folder
        self.hits = set()
        self.reads = set()

    def call(self, name, args):
        if name not in self.schema or not isinstance(args, dict):
            return {"ok": False, "error": "unsupported_call"}
        parameter = self.schema[name]["parameters"]
        if set(args) != set(parameter["required"]):
            return {"ok": False, "error": "invalid_arguments"}
        value = next(iter(args.values()))
        if name == "search_sources":
            if not isinstance(value, list) or not value or not all(isinstance(x, str) for x in value):
                return {"ok": False, "error": "invalid_terms"}
            hits = [dict(id=s["id"], topic=s["topic"], title=s["title"])
                    for s in self.sources.values() if set(value) <= set(s["tags"])]
            self.hits = {hit["id"] for hit in hits}
            return {"ok": True, "hits": hits}
        if not isinstance(value, str) or not value:
            return {"ok": False, "error": "invalid_string"}
        if name == "read_source":
            if value not in self.hits:
                return {"ok": False, "error": "source_not_in_search"}
            self.reads.add(value)
            return {"ok": True, "source": self.sources[value]}
        if len(self.reads) != self.contract["required_sources"]:
            return {"ok": False, "error": "reads_incomplete"}
        path = self.folder / self.contract["output"]
        path.write_text(value, encoding="utf-8")
        return {"ok": True, "artifact": path.name, "sha256": digest(path)}


def choose(contract, observations):
    if not observations:
        return "search_sources", {"terms": contract["query"]}, "先检索相关资料"
    hits = observations[0]["hits"]
    read = [item["source"] for item in observations[1:] if "source" in item]
    covered = {source["topic"] for source in read}
    for topic in contract["topics"]:
        if topic not in covered:
            match = next((hit for hit in hits if hit["topic"] == topic), None)
            if match is None:
                return None
            return "read_source", {"source_id": match["id"]}, f"读取{topic}议题的资料"
    return "write_brief", {"markdown": compose(read)}, "把已读证据汇编成简报"


def run(budget, contract, schema, sources, out):
    run_id = f"steps-{budget}"
    folder = out / run_id
    folder.mkdir(parents=True, exist_ok=True)
    artifact = folder / contract["output"]
    if artifact.exists():
        artifact.unlink()
    tools = Tools(sources, contract, schema, folder)
    calls, results, observations = [], [], []
    reason = "budget_exhausted"
    for step in range(1, budget + 1):
        decision = choose(contract, observations)
        if decision is None:
            reason = "missing_topic"
            break
        name, args, note = decision
        call_id = f"{run_id}:{step}"
        calls.append(dict(run_id=run_id, step=step, call_id=call_id,
                          tool=name, arguments=args, decision_note=note))
        result = tools.call(name, args)
        results.append(dict(run_id=run_id, step=step, call_id=call_id, tool=name, result=result))
        observations.append(result)
        if not result["ok"]:
            reason = "tool_error"
            break
        if name == "write_brief":
            reason = "submitted"
            break
    calls.append(dict(run_id=run_id, event="stop", steps_used=len(results), reason=reason))
    return calls, results


def main():
    from validate import evaluate

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    contract = load(ROOT / "task-contract.json")
    schema = load(ROOT / "tool-schema.json")
    sources = load(ROOT / contract["fixture"])
    all_calls, all_results = [], []
    for budget in (3, 6):
        calls, results = run(budget, contract, schema, sources, out)
        all_calls.extend(calls)
        all_results.extend(results)
    write_jsonl(out / "trajectory.jsonl", all_calls)
    write_jsonl(out / "tool-results.jsonl", all_results)
    best = out / "steps-6" / contract["output"]
    (out / contract["output"]).write_bytes(best.read_bytes())
    rows = evaluate(out)
    with (out / "evaluation.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    provenance = {
        "task_id": contract["task_id"],
        "fixture_origin": "本作业自建。S01–S03 为Codex 辅助整理的论文摘要卡，D01–D02 为合成干扰项。",
        "artifact_origin": "Codex 辅助查证论文并编写资料卡和代码。简报、轨迹、工具结果和评分由实际离线执行生成。",
        "policy": "deterministic_rule_controller",
        "runtime_model": None,
        "runtime_api": None,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "conditions": [{"run_id": "steps-3", "max_steps": 3}, {"run_id": "steps-6", "max_steps": 6}],
        "input_sha256": {name: digest(ROOT / name) for name in INPUTS},
        "output_sha256": {name: digest(out / name) for name in
                          ("trajectory.jsonl", "tool-results.jsonl", "evaluation.csv",
                           contract["output"], "steps-6/final-brief.md")}
    }
    (out / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2)
                                         + "\n", encoding="utf-8")
    for row in rows:
        print(f"{row['run_id']}: {row['status']}, calls={row['tool_calls']}, "
              f"reads={row['unique_relevant_reads']}, checks={row['checks_passed']}/5")


if __name__ == "__main__":
    main()
