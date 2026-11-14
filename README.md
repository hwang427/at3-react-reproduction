# AT3 與 AT4 作業查閱入口

| 作業 | 查閱材料 |
| --- | --- |
| **AT3 ② 技術復現** | [復現說明](复现说明.md) · [模型對照報告](模型对照报告.md) · [規則復現程式](reproduce.py) · [同模型實驗程式](model_experiment.py) · [逐題結果](model-results/evaluation.csv) · [結果截圖](model-results/result.png) |
| **AT4 期末整合報告** | 論文 PDF 隨課程作業提交 · [環境依賴](requirements.txt) · [程式和資料](src/) · [實驗結果](results/) |

AT3 ① 文獻綜述與 ③ Agent 工作任務的原始材料隨 AT3 作業提交。[③ 簡報](results/budget-final-brief.md) · [工具軌跡](results/budget-trajectory.jsonl) · [工具回傳](results/budget-tool-results.jsonl) · [驗收結果](results/budget-evaluation.csv)

## AT4 實驗與重跑

[模型對照](results/model-evaluation.csv) · [步數對照](results/budget-evaluation.csv) · [檢索對照](results/retrieval-evaluation.csv)

離線規則實驗可用 Python 3.9+ 標準庫。語言模型實驗使用 Python 3.13 及 requirements.txt，首次執行需下載約 1 GB 權重，可用 --model 指定本機模型目錄。

```sh
python -B src/run_agent.py --out runs/budget
python -B src/validate.py --out runs/budget
python -B src/retrieval_test.py --out runs/retrieval
python -m pip install -r requirements.txt
python -B src/model_experiment.py --revision 7ae557604adf67be50417f59c2c2f167def9a775 --out runs/model
```

模型結果沿用 AT3 的 24 條實際推理記錄。步數與檢索實驗可用上述程式重跑，檢索詞表涵蓋本次測試的已知變體。Codex 輔助查證、實作與寫作。
