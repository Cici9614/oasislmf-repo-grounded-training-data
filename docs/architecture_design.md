# Architecture Design — Repo-Grounded Training Data Generation (OasisLMF)

## 1. 背景与目标
训练数据质量直接决定模型对“本地代码仓问题”的回答能力。本项目构建一个可复现流水线，从 OasisLMF 代码仓自动生成两类训练数据，并提供质量控制与结构校验。

目标：
- Repo-grounded：所有答案均来自仓库可追溯证据
- 可解释：样本含 reasoning_trace，明确引用证据
- 可复现：脚本运行即可生成相同格式数据
- 可扩展：后续可替换/增强 analyzer 与 generator

## 2. OasisLMF 业务路径（概览）
OasisLMF 将 Exposure（资产暴露）与 Hazard（灾害强度）与 Vulnerability（脆弱性）结合，先计算 GUL，再通过 Financial Module（FM）应用保险/再保险条款，最终聚合输出损失结果（GUL/IL/RIL 等）。

## Requirements (Minimal)
本项目以三条最小业务需求驱动数据生成（详见 docs/requirements.md）：
- R1：可解释性与可追溯
- R2：金融条款基本约束
- R3：报告与汇总输出（EP/TVaR 等）

## 3. 系统架构
数据流（v0 实现）：
data/raw_repo (OasisLMF)
↓
analyzer: AST 扫描 → 抽取 class/function + docstring + 代码片段（chunk）
↓
generator: 生成 QA/Design 样本（repo-grounded）
↓
validator: pydantic 校验（结构一致性）
↓
data/final_datasets: train/dev/test.jsonl

### 3.1 中间产物（data/intermediate）
为保证“可追溯”和“可复现”，analyzer 会在生成最终训练集之前产出可审计的中间索引文件：

- `data/intermediate/catalog.json`
  - 含义：chunk 索引（证据库），记录每个可用代码片段的：
    - `path`（仓库相对路径）、`name`（符号名）、`symbol_type`（class/function）
    - `lineno/end_lineno`（定义位置）、`docstring`（文档注释）、`content`（snippet 证据）
  - 用途：为后续数据生成提供“可引用证据集合”，确保 repo-grounded。

- `data/intermediate/catalog_stats.json`
  - 含义：覆盖率统计（写报告用），例如：
    - 总 chunk 数
    - 按 `business_stage`（exposure/hazard/gul/fm/aggregation/other）分布
    - 按 `symbol_type`（class/function）分布
  - 用途：用于评估数据覆盖面与后续扩展方向。

## 4. 模块职责
### 4.1 analyzer（静态分析）
- 输入：仓库路径 data/raw_repo
- 处理：递归扫描 *.py，AST 解析 class/function
- 产出：CodeItem/Chunk（path/name/lineno/end_lineno/docstring/snippet）
- 说明：该版本优先提取带 docstring 的 public symbol，降低噪声

### 4.2 generator（数据生成）
- 场景 1：QA（事实类）
  - 问题：某符号负责什么功能？
  - 证据：代码片段 + docstring（context）
  - trace：定位 → 总结
- 场景 2：Design（受约束设计）
  - 问题：在不破坏现有调用方的前提下如何扩展支持新格式/字段？
  - 要求：必须引用当前符号定义位置，不引入仓库中不存在的机制（避免幻觉）

### 4.3 validator（质量控制：结构校验）
- 采用 pydantic 定义 TrainingSample schema
- 对生成样本逐条校验，确保：
  - 字段齐全且类型正确
  - evidence_ref 与 context.path 可追溯

## 5. 训练样本 Schema（核心字段）
每条样本结构：
- id
- task_type: qa | design
- instruction
- context: [{source_type, path, content}]
- reasoning_trace: [{step, goal, evidence_ref, intermediate_conclusion}]
- output
- metadata: {repo, business_stage, question_id, difficulty, language}

## 6. 数据切分策略
- 按 80/10/10 切分为 train/dev/test
- 目前采用随机切分（固定 SEED），保证可复现

## 7. 质量与风险控制
### 7.1 Repo-grounded 证据
- context 中包含真实代码片段（snippet）与 docstring
- output 与 trace 必须引用同一文件 path（evidence_ref）

### 7.2 已知限制
- 当前版本已产出 chunk catalog（见 3.1），但主要证据仍集中在“代码 + docstring”；后续可扩展覆盖文档/配置/CLI 参数说明等非代码证据源
- Python 3.12 解析上游源码可能出现 SyntaxWarning，不影响数据生成与校验

## 8. 后续扩展（v1）
- 在已有 catalog 的基础上，进一步增强分阶段映射规则（提升 business_stage 命中率）
- 扩展 validator：去重、覆盖率统计、异常类 QA（输入缺失/边界情况）
- 可选：使用 final_datasets 进行 LoRA 微调并给出对比评估

## 9. 如何复现（3 条命令）
在项目根目录执行以下命令即可完整复现中间产物与最终数据集：

```powershell
# 1) 生成 chunk 索引与统计（intermediate）
python -m src.analyzer.build_catalog

# 2) 生成训练数据集（final_datasets）
python -m src.generator.generate_oasis_dataset

# 3) 校验输出数据结构（示例：train）
python -m src.validator.validate_jsonl --path data/final_datasets/train.jsonl
