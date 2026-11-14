# 如何评估能调用工具的 Agent

同一个 Agent 的工具调用可以看起来合理，但是否完成任务仍需检查外部结果。下面三个维度分别对应行动过程、任务终态和跨次可靠性。

- **行动策略**　ReAct 将文字推理与工具行动交织，用环境观察更新计划。HotpotQA 精确匹配率为 27.4%，Act 为 25.7%。 [S01 · ReAct · §2、§3.3、表 1](https://arxiv.org/html/2210.03629)
- **任务完成**　WebArena 在模拟网站中通过功能性检查评估任务。最佳 GPT-4 Agent 的端到端成功率为 14.41%，人类为 78.24%。 [S02 · WebArena · §3、§5、表 2](https://proceedings.iclr.cc/paper_files/paper/2024/file/4410c0711e9154a7a2d26f9b3816d1ef-Paper-Conference.pdf)
- **重复可靠性**　τ-bench 比对会话结束后的数据库状态，并用 pass^k 衡量 k 次试验均成功的可靠性。论文报告 GPT-4o 的零售 pass^8 低于 25%。 [S03 · τ-bench · §2–3、图 4](https://proceedings.iclr.cc/paper_files/paper/2025/file/1b126cc38b8638e07bef37e7b2bb72bf-Paper-Conference.pdf)

## 对实验设计的启示

先记录可复查的工具与观察，再用独立检查器判定产物。若涉及随机模型，再对同一任务重复运行，报告多次均成功的比例。上述三篇研究的任务和指标各异，百分比仅用于说明各自的结果。
