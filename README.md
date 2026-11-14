# AT4｜工具型 Agent 的行動與驗收

本報告延續 AT3，研究同一模型在 Act 與 ReAct 提示下的工具行動，以及離線來源整理對步數與檢索方式的敏感性。

- [期末論文](paper.pdf)
- [模型對照](results/model-evaluation.csv) · [步數對照](results/budget-evaluation.csv) · [檢索對照](results/retrieval-evaluation.csv)
- `src/` 包含 Python 程式、問答資料、來源包及工具介面。結果目錄含逐題軌跡、工具返回、來源記錄及結果圖。

## 重跑

離線規則實驗可用 Python 3.9+ 標準庫。語言模型實驗用 Python 3.13 和 `requirements.txt`，首次執行需下載約 1 GB 權重。亦可用 `--model` 指定已下載的目錄。

```sh
python -B src/run_agent.py --out runs/budget
python -B src/validate.py --out runs/budget
python -B src/retrieval_test.py --out runs/retrieval
python -m pip install -r requirements.txt
python -B src/model_experiment.py --revision 7ae557604adf67be50417f59c2c2f167def9a775 --out runs/model
```

模型結果沿用 AT3 的 24 條實際推理記錄。步數實驗以此目錄中的程式重跑。檢索實驗的詞表預先涵蓋所有測試變體，結果用於檢查已知詞形差異。執行時的工具僅讀取隨附資料、寫入指定輸出目錄。Codex 輔助查證、實作與寫作。
