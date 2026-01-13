# Sample Trace Report (Repo-Grounded)

本文档展示本项目生成的样本在两个场景下的“可追溯推理（reasoning_trace）”与“证据绑定（context/evidence_ref）”效果。
样本来自 `data/final_datasets/test.jsonl`（节选）。

---

## Sample A — Design (Constrained, Repo-Grounded)
**Covers:** R1（可解释性与可追溯）

**ID:** `design_auto_0048`  
**Task Type:** `design`  
**Evidence Path:** `oasislmf/cli/model.py`

### Instruction
设计题：假设需要让 `GenerateComputationSettingsJsonSchema` 支持一种新的输入数据格式/字段，但要求不破坏现有调用方。请基于当前代码结构给出可实施的扩展方案，并指出可能修改的文件与位置。

### Context (Evidence)
- `path`: `oasislmf/cli/model.py`
- 证据要点：
  - 类 `GenerateComputationSettingsJsonSchema` 定义位置约在第 122 行附近
  - docstring 指向其职责：生成 computation settings 的 json schema

### Reasoning Trace（节选）
1. 确认组件职责与边界（引用 `oasislmf/cli/model.py`）
2. 提出兼容性优先策略（引用 `oasislmf/cli/model.py`）

### Output（节选）
- 保持接口契约不变，在内部引入“适配层/解析函数”支持新字段/新格式
- 将新增解析逻辑封装隔离，避免破坏现有调用链
- 修改位置：优先在 `oasislmf/cli/model.py` 的类定义附近扩展解析/分派，并同步入口校验与说明

---

## Sample B — QA (Fact)
**Covers:** R1（可解释性与可追溯）

**ID:** `qa_auto_0155`  
**Task Type:** `qa`  
**Evidence Path:** `oasislmf/utils/log_config.py`

### Instruction
在 OasisLMF 项目中，`oasislmf/utils/log_config.py` 文件里的 `validate_config` 主要负责什么功能？请根据代码与文档注释回答。

### Context (Evidence)
- `path`: `oasislmf/utils/log_config.py`
- 证据要点：
  - function `validate_config`（约 212 行附近）
  - docstring：Validate logging configuration and return any issues.

### Reasoning Trace（节选）
1. 定位符号定义与 docstring（引用 `oasislmf/utils/log_config.py`）
2. 基于 docstring/实现总结功能（引用 `oasislmf/utils/log_config.py`）

### Output（节选）
- `validate_config` 用于校验 logging 配置并返回潜在问题/警告信息（证据：docstring + 代码片段）

---

## Sample C — QA (FM-related Fact)
**Covers:** R2（金融条款基本约束）

**ID:** `qa_auto_0130`  
**Task Type:** `qa`  
**Evidence Path:** `oasislmf/utils/profiles.py`

### Instruction
在 OasisLMF 项目中，`oasislmf/utils/profiles.py` 文件里的 `get_grouped_fm_profile_by_level_and_term_group` 主要负责什么功能？请根据代码与文档注释回答。

### Context (Evidence)
- `path`: `oasislmf/utils/profiles.py`
- 证据要点：
  - function `get_grouped_fm_profile_by_level_and_term_group`（约 44 行附近）
  - docstring 描述其用于 grouped exposure/accounts profile，并涉及多个 FM levels 与 term grouping

### Reasoning Trace（节选）
1. 定位符号定义与 docstring（引用 `oasislmf/utils/profiles.py`）
2. 基于 docstring/实现总结功能（引用 `oasislmf/utils/profiles.py`）

### Output（节选）
- 该函数用于生成按 level 与 term group 分组的 FM profile，描述 exposure/accounts 中的金融条款结构，为后续 FM 处理提供统一结构。
---

## Sample D — QA (Reporting/TVaR)
**Covers:** R3（报告与汇总输出）

**ID:** `qa_auto_0071`  
**Task Type:** `qa`  
**Evidence Path:** `oasislmf/pytools/lec/aggreports/write_tables.py`

### Instruction
在 OasisLMF 项目中，`oasislmf/pytools/lec/aggreports/write_tables.py` 文件里的 `write_tvar_wheatsheaf` 主要负责什么功能？请根据代码与文档注释回答。

### Context (Evidence)
- `path`: `oasislmf/pytools/lec/aggreports/write_tables.py`
- 证据要点：
  - function `write_tvar_wheatsheaf`（约 247–268 行）
  - docstring 指向其职责：Get TVaR values for PSEPT output from tail
  - 返回结构：`rets` 列表，包含 `(summary_id, sidx, eptype_tvar, retperiod, tvar)` 等字段

### Reasoning Trace（节选）
1. 定位目标符号的定义与职责描述（引用 `oasislmf/pytools/lec/aggreports/write_tables.py`）
2. 基于 docstring/实现总结其主要功能（引用 `oasislmf/pytools/lec/aggreports/write_tables.py`）

### Output（节选）
- `write_tvar_wheatsheaf` 的核心职责是：从 `tail` 中提取 TVaR（Tail Value-at-Risk）相关结果，生成用于 PSEPT 输出的 `(return period, tvar)` 表格数据，并按 `tail.keys()` 排序后逐条写入 `rets` 返回。
- 证据：docstring 首句 “Get TVaR values for PSEPT output from tail”，以及函数实现中对 `tail` 的遍历与 `rets.append((summary_id, sidx, eptype_tvar, row["retperiod"], row["tvar"]))` 组装逻辑。
