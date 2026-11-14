# AT3 ②｜ReAct 核心循环复现

在离线小语料上复现 **Search → Observation → 下一次动作 → Finish**。ReAct 路径为每个动作记录显式子目标，并在摘要缺少字段时执行 Lookup。只需要 Python 3.9+，无需安装依赖。

```sh
python3 reproduce.py
# 可选：输出到独立目录，保留本次提交的结果
python3 reproduce.py --out fresh-results
```

- `cases.json`：12 条自建合成任务，4 条答案在第二跳摘要，8 条在正文。虚构名称与地点用于避免外部知识捷径。
- `reproduce.py`：状态化工具环境、两种控制策略、归一化精确匹配及记录。
- `results/`：本次运行的逐例评估、24 条轨迹、终端摘要和结果截图。
- `复现说明.md`：方法映射、结果对照及限制。

论文：[ReAct，ICLR 2023，§2、§3、表 1](https://arxiv.org/html/2210.03629)。[作者实现](https://github.com/ysymyth/ReAct)。

## 同一语言模型的 Act／ReAct 对照

增强实验使用 Qwen2.5-0.5B-Instruct，对同一份 `cases.json` 逐题成对运行。两组共享 Search、Lookup 和 Finish，每题最多 5 轮，每轮最多生成 96 个 token。ReAct 提示在行动前输出一句 Thought，两组共享同一示例的动作和观察。首次运行需下载约 1 GB 的模型权重。

```sh
python -m pip install -r requirements-model.txt
python -B model_experiment.py --revision 7ae557604adf67be50417f59c2c2f167def9a775 --out fresh-model-results
```

使用本地模型目录时，加上 `--model /path/to/local/model`。运行环境、完整提示、模型版本、文件哈希见 `model-results/provenance.json`。逐题精确匹配、失败类型及工具次数见 `model-results/evaluation.csv`，模型原始输出和工具观察见 `model-results/trajectory.jsonl`。原先的 `reproduce.py` 和 `results/` 对应规则演示，正式模型对照见《模型对照报告》及 `model-results/`。

[模型卡](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct)
