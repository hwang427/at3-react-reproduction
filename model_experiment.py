"""Run matched Act and ReAct prompts against a local causal language model."""
import argparse
import csv
import hashlib
from functools import partial
import json
import platform
import re
from collections import Counter
from pathlib import Path

from reproduce import Wiki, field, normalized

ROOT = Path(__file__).resolve().parent
BUDGET = 5
TOKENS = 96
MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"

TOOLS = """根据资料回答项目负责机构所在区。每轮只调用一个工具。
Search[标题]：返回页面摘要，并设置当前页面。
Lookup[字段]：在当前页面中查找字段，例如 Lookup[所在区]。
Finish[答案]：提交所在区名称并结束。
Search 需要精确的标题。最终答案只写区名。"""

EXAMPLE = [
    ("先查项目页。", "Search[湖镜计划]", "负责机构=湖光研究组。"),
    ("根据观察，查湖光研究组。", "Search[湖光研究组]", "建立于湖岸。"),
    ("摘要缺少区名，回查当前页。", "Lookup[所在区]", "所在区=镜湖区。"),
    ("已有区名，提交。", "Finish[镜湖区]", None),
]


def system_prompt(mode):
    rule = ("先输出一句简短的 Thought:，再输出 Action:。"
            if mode == "react" else "只输出 Action: 行。")
    lines = [TOOLS, rule, "示例问题：湖镜计划的负责机构位于哪个区？"]
    for thought, action, observation in EXAMPLE:
        if mode == "react":
            lines.append(f"Thought: {thought}")
        lines.append(f"Action: {action}")
        if observation:
            lines.append(f"Observation: {observation}")
    return "\n".join(lines)


def evaluate_case(generate, pages, project, expected, mode):
    wiki = Wiki(pages)
    messages = [dict(role="system", content=system_prompt(mode)),
                dict(role="user", content=f"{project}的负责机构位于哪个区？")]
    events = []
    seen = set()
    failure = "budget_exhausted"
    for step in range(1, BUDGET + 1):
        raw = generate(messages)
        event = {"step": step, "raw_model_output": raw}
        events.append(event)
        first_turn = re.split(r"(?im)^\s*Observation\s*[:：]", raw, maxsplit=1)[0]
        actions = re.findall(
            r"(?im)^\s*(?:Action\s*[:：]\s*)?(Search|Lookup|Finish)\s*[\[［]([^\]］\n]+)[\]］]",
            first_turn,
        )
        event["thought_present"] = bool(re.search(r"(?im)^\s*Thought\s*[:：]\s*\S", first_turn))
        if len(actions) != 1:
            failure = "invalid_action_format"
            break
        action, argument = actions[0][0].capitalize(), actions[0][1].strip()
        observation = wiki.step(action, argument)
        event.update(action=action, argument=argument, observation=observation)
        district = field(observation, "所在区")
        if district:
            seen.add(normalized(district))
        if action == "Finish":
            if normalized(wiki.answer) == normalized(expected):
                failure = ""
            else:
                failure = ("wrong_answer_after_evidence" if normalized(expected) in seen
                           else "wrong_answer_without_evidence")
            break
        messages.extend([dict(role="assistant", content=first_turn.strip()),
                         dict(role="user", content=f"Observation: {observation}\n继续，给出下一步。")])
    return wiki.answer, failure, events


def main():
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=MODEL_ID, help="Model ID or downloaded local directory")
    parser.add_argument("--revision", help="Optional Hugging Face commit SHA")
    parser.add_argument("--out", type=Path, default=ROOT / "model-results")
    args = parser.parse_args()
    torch.set_num_threads(4)
    tokenizer = AutoTokenizer.from_pretrained(args.model, revision=args.revision)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, revision=args.revision, dtype=torch.float32
    ).eval()

    @torch.inference_mode()
    def generate(messages):
        batch = tokenizer.apply_chat_template(messages, add_generation_prompt=True,
                                              tokenize=True, return_dict=True,
                                              return_tensors="pt")
        output = model.generate(**batch, do_sample=False, max_new_tokens=TOKENS,
                                pad_token_id=tokenizer.eos_token_id, tokenizer=tokenizer,
                                stop_strings=["\nObservation:", "\nObservation："])
        return tokenizer.decode(output[0, batch["input_ids"].shape[1]:],
                                skip_special_tokens=True).strip()

    path = ROOT / "cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    pages = {}
    for project, org, district, placement in cases:
        pages[project] = [f"负责机构={org}。"]
        lead, detail = f"所在区={district}。", "设有数据档案室。"
        pages[org] = [lead, detail] if placement == "lead" else [detail, lead]

    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    with (args.out / "trajectory.jsonl").open("w", encoding="utf-8") as log:
        for project, _, expected, placement in cases:
            for mode in ("act", "react"):
                answer, failure, events = evaluate_case(generate, pages, project, expected, mode)
                row = dict(case=project, placement=placement, mode=mode, answer=answer or "",
                           expected=expected, exact_match=int(not failure), failure_type=failure,
                           tool_calls=sum("action" in event for event in events),
                           lookup_calls=sum(event.get("action") == "Lookup" for event in events),
                           thought_steps=sum(event["thought_present"] for event in events))
                rows.append(row)
                log.write(json.dumps(dict(row, events=events), ensure_ascii=False) + "\n")
                log.flush()
                print(mode, project, answer, failure or "exact match", flush=True)
    with (args.out / "evaluation.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    def sha(file):
        with file.open("rb") as stream:
            digest = hashlib.sha256()
            for chunk in iter(partial(stream.read, 1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    weights = Path(args.model) / "model.safetensors"
    provenance = dict(model=MODEL_ID, revision=args.revision or getattr(model.config, "_commit_hash", None),
                      local_weights_sha256=sha(weights) if weights.is_file() else None,
                      decoding="greedy", dtype="float32", device="cpu", threads=4,
                      max_rounds=BUDGET, max_new_tokens_per_round=TOKENS,
                      python=platform.python_version(), torch=torch.__version__,
                      transformers=transformers.__version__, cases_sha256=sha(path),
                      script_sha256=sha(Path(__file__)),
                      tool_code_sha256=sha(ROOT / "reproduce.py"),
                      prompts={mode:system_prompt(mode) for mode in ("act", "react")})
    (args.out / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [f"Model: {MODEL_ID} | CPU | greedy | 5 rounds | 12 paired cases"]
    for mode in ("act", "react"):
        group = [row for row in rows if row["mode"] == mode]
        exact = sum(row["exact_match"] for row in group)
        failures = Counter(row["failure_type"] for row in group if row["failure_type"])
        lines.append(f"{mode:5} EM={exact}/{len(group)} ({exact / len(group):.1%})  "
                     f"calls={sum(r['tool_calls'] for r in group)}  "
                     f"Lookup={sum(r['lookup_calls'] for r in group)}")
        lines.extend(f"  {key}: {count}" for key, count in sorted(failures.items()))
    summary = "\n".join(lines) + "\n"
    (args.out / "summary.txt").write_text(summary, encoding="utf-8")
    print(summary, end="")


if __name__ == "__main__":
    main()
