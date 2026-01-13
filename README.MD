# LLM Training Data Generator (Repo-Grounded) — OasisLMF Case Study

## 1. 项目目标

本项目面向“本地代码仓智能训练数据生成与处理”作业要求，构建一个可复现的数据生成流水线：

- 以 OasisLMF 代码仓为唯一事实来源（repo-grounded）
- 自动抽取代码片段（chunk）作为上下文证据，并生成可审计索引（catalog）
- 生成两类训练样本：
  - **场景 1：事实类 QA**（代码职责/规则解释）
  - **场景 2：受约束设计题**（基于现有结构提出扩展方案，并强制引用仓库证据）
- 输出可用于训练/微调的 JSONL 数据集，并提供结构化校验闭环

**说明**：本项目核心交付物是训练数据与生成/校验系统，不要求接入外部 LLM API。

## 2. Requirements (Minimal)

本项目以三条最小业务需求驱动训练数据生成：

- **R1 可解释性与可追溯**：每条样本包含代码证据（context）与推理轨迹（reasoning_trace）
- **R2 金融条款基本约束**：面向 FM 条款结构与约束规则相关问答/设计
- **R3 报告与汇总输出**：面向 EP/TVaR 等汇总表生成与一致性相关问答

详见：`docs/requirements.md`

## 3. 仓库业务背景（OasisLMF）

OasisLMF 是灾害风险量化与金融损失评估系统，结合 Exposure / Hazard / Vulnerability 与金融条款（FM），输出 GUL/IL/RIL 等损失结果。

## 4. 目录结构

```text
oasislmf-repo-grounded-training-data/
├── data/
│   ├── raw_repo/                 # OasisLMF 源码（clone 或解压后放入）
│   ├── intermediate/             # analyzer 输出：catalog 与统计
│   └── final_datasets/           # 最终交付：train/dev/test.jsonl
├── src/
│   ├── analyzer/                 # 生成 chunk 索引（catalog）
│   ├── generator/                # 生成训练数据集（QA + Design）
│   └── validator/                # schema 定义与 JSONL 校验
├── docs/
│   ├── architecture_design.md    # 系统设计文档
│   ├── requirements.md           # 最小需求定义
│   └── sample_trace_report.md    # 样例（含 Covers R?）
└── README.md
```

## 5. 环境依赖

-Python 3.10+（已在 Python 3.12 验证）

**依赖安装：**

```bash
pip install pydantic
```

## 6. 如何运行（Windows / PyCharm）

在项目根目录执行以下命令即可复现全部产物：

```powershell
# 1) 生成中间索引（chunk catalog + stats）
python -m src.analyzer.build_catalog

# 2) 生成训练数据集（场景 1 QA + 场景 2 Design）
python -m src.generator.generate_oasis_dataset

# 3) 校验输出数据结构（示例：train）
python -m src.validator.validate_jsonl --path data/final_datasets/train.jsonl
```

## 7. 输出产物

中间产物（可审计）：

- `data/intermediate/catalog.json`
- `data/intermediate/catalog_stats.json`

最终数据集（可用于训练/微调）：

- `data/final_datasets/train.jsonl`
- `data/final_datasets/dev.jsonl`
- `data/final_datasets/test.jsonl`

## 8. 文档说明

- `docs/architecture_design.md`：架构、模块职责、Schema、质检策略、复现方式
- `docs/requirements.md`：三条最小业务需求定义
- `docs/sample_trace_report.md` 提供可审计样例：2 条事实 QA + 1 条受约束 Design，均从 `data/final_datasets/test.jsonl` 节选，并标注 Covers（R1/R2/R3）。
