
# coding: utf-8

import ast
import json
import os
import random
from dataclasses import dataclass
from glob import glob
from pathlib import Path
from typing import List, Optional, Tuple

from src.validator.sample_schema import TrainingSample

# ============== 配置区（按你的目录结构） ==============
ROOT = Path(__file__).resolve().parents[2]

REPO_PATH = ROOT / "data" / "raw_repo"
OUT_DIR = ROOT / "data" / "final_datasets"
SEED = 42
N_QA = 200
N_DESIGN = 50

MAX_SNIPPET_LINES = 80    # 单个 context 代码片段最大行数，避免太长
# ====================================================

SKIP_DIR_KEYWORDS = ("venv", ".venv", "__pycache__", ".tox", "site-packages", "dist-packages")
SKIP_FILE_KEYWORDS = ("test", "tests")

@dataclass
class CodeItem:
    rel_path: str
    node_type: str               # "class" or "function"
    name: str
    lineno: int
    end_lineno: int
    docstring: str
    snippet: str
    business_stage: str

def detect_stage(rel_path: str) -> str:
    p = rel_path.lower()
    # 轻量启发式：够用且可解释；后续可用 catalog 精化
    if any(k in p for k in ("exposure", "location", "expos")):
        return "exposure"
    if any(k in p for k in ("hazard", "peril", "event", "occurrence")):
        return "hazard"
    if any(k in p for k in ("gul", "loss", "groundup")):
        return "gul"
    if any(k in p for k in ("fm", "financial", "terms", "reinsurance")):
        return "fm"
    if any(k in p for k in ("aggregation", "summary", "report")):
        return "aggregation"
    return "other"

def should_skip_file(path: str) -> bool:
    lp = path.lower()
    if any(k in lp for k in SKIP_DIR_KEYWORDS):
        return True
    if any(k in os.path.basename(lp) for k in SKIP_FILE_KEYWORDS):
        return True
    return False

def safe_read_text(fp: Path) -> Optional[str]:
    try:
        return fp.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # 兜底：忽略坏字符，保证 pipeline 不崩
        try:
            return fp.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None
    except Exception:
        return None

def extract_snippet(lines: List[str], lineno: int, end_lineno: int) -> str:
    start = max(lineno - 1, 0)
    end = min(end_lineno, len(lines))
    # 控制最大行数，避免上下文过长
    if end - start > MAX_SNIPPET_LINES:
        end = start + MAX_SNIPPET_LINES
    return "".join(lines[start:end]).rstrip()

class CodeAnalyzer:
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.items: List[CodeItem] = []
        self.parse_errors: List[Tuple[str, str]] = []

    def scan(self) -> None:
        pattern = str(self.repo_path / "**" / "*.py")
        files = glob(pattern, recursive=True)
        files = [f for f in files if not should_skip_file(f)]

        print(f"Scanning repo: {self.repo_path.resolve()}")
        print(f"Found {len(files)} python files (after filtering).")

        for f in files:
            self._parse_file(Path(f))

        print(f"Extracted {len(self.items)} code items.")
        if self.parse_errors:
            print(f"Parse errors: {len(self.parse_errors)} (kept for debugging)")

    def _parse_file(self, fp: Path) -> None:
        content = safe_read_text(fp)
        if content is None:
            self.parse_errors.append((str(fp), "read_failed"))
            return

        try:
            tree = ast.parse(content)
        except Exception as e:
            self.parse_errors.append((str(fp), f"ast_parse_failed: {e}"))
            return

        lines = content.splitlines(keepends=True)
        rel_path = str(fp.relative_to(self.repo_path)).replace("\\", "/")

        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                name = getattr(node, "name", "")
                # 跳过私有 / 魔法
                if not name or name.startswith("_"):
                    continue

                doc = ast.get_docstring(node)
                # 没 docstring 的项噪音大：先不收（你后续可放宽）
                if not doc or len(doc.strip()) < 10:
                    continue

                lineno = getattr(node, "lineno", 1)
                end_lineno = getattr(node, "end_lineno", lineno)
                snippet = extract_snippet(lines, lineno, end_lineno)

                item = CodeItem(
                    rel_path=rel_path,
                    node_type="class" if isinstance(node, ast.ClassDef) else "function",
                    name=name,
                    lineno=lineno,
                    end_lineno=end_lineno,
                    docstring=doc.strip(),
                    snippet=snippet,
                    business_stage=detect_stage(rel_path),
                )
                self.items.append(item)

class DatasetGenerator:
    def __init__(self, items: List[CodeItem], seed: int = 42):
        self.items = items
        self.rng = random.Random(seed)

    def _context_for_item(self, it: CodeItem):
        # 真正 repo-grounded：把“代码片段”作为 context
        # 同时把 docstring 拼进去，帮助模型理解职责
        content = (
            f"# File: {it.rel_path}\n"
            f"# {it.node_type}: {it.name} (lines {it.lineno}-{it.end_lineno})\n\n"
            f"{it.snippet}\n\n"
            f'"""Docstring (excerpt)"""\n{it.docstring}\n'
        )
        return [{
            "source_type": "code",
            "path": it.rel_path,
            "content": content.strip()
        }]

    def create_fact_qa(self, it: CodeItem, idx: int):
        instruction = f"在 OasisLMF 项目中，`{it.rel_path}` 文件里的 `{it.name}` 主要负责什么功能？请根据代码与文档注释回答。"

        doc_first = it.docstring.splitlines()[0].strip()
        output = (
            f"`{it.name}`（位于 `{it.rel_path}`）的主要职责可以从其 docstring 与实现片段看出：\n"
            f"- 核心描述：{doc_first}\n\n"
            f"证据：该定义出现在文件 `{it.rel_path}` 的第 {it.lineno} 行附近。"
        )

        reasoning_trace = [
            {
                "step": 1,
                "goal": "定位目标符号的定义与职责描述",
                "evidence_ref": [it.rel_path],
                "intermediate_conclusion": f"在 `{it.rel_path}` 中找到 `{it.name}` 的定义及 docstring。"
            },
            {
                "step": 2,
                "goal": "基于 docstring/实现总结其主要功能",
                "evidence_ref": [it.rel_path],
                "intermediate_conclusion": f"docstring 的首句可作为 `{it.name}` 职责的高置信摘要。"
            }
        ]

        sample = {
            "id": f"qa_auto_{idx:04d}",
            "task_type": "qa",
            "instruction": instruction,
            "context": self._context_for_item(it),
            "reasoning_trace": reasoning_trace,
            "output": output,
            "metadata": {
                "repo": "OasisLMF",
                "business_stage": it.business_stage,
                "question_id": "AUTO_FACT",
                "difficulty": "easy",
                "language": "zh"
            }
        }
        TrainingSample.model_validate(sample)
        return sample

    def create_design(self, it: CodeItem, idx: int):
        # 受约束设计：不假设 repo 存在 factory.py；强调兼容性、扩展点、修改位置与证据
        instruction = (
            f"设计题：假设需要让 `{it.name}` 支持一种新的输入数据格式/字段，但要求不破坏现有调用方。"
            f"请基于当前代码结构给出可实施的扩展方案，并指出可能修改的文件与位置。"
        )

        output = (
            f"基于 `{it.rel_path}` 中 `{it.name}` 的职责（见 docstring 与实现片段），在保持向后兼容的前提下可采用：\n"
            f"1) 接口兼容：保留现有入参/返回契约，在内部引入“适配层/解析函数”处理新格式。\n"
            f"2) 扩展点隔离：将新格式解析逻辑封装为独立函数/类，避免把分支逻辑散落在主流程。\n"
            f"3) 渐进式切换：为新格式增加单测与示例；必要时在文档中声明支持范围。\n"
            f"4) 修改位置：优先在 `{it.rel_path}` 的 `{it.name}` 定义附近（约第 {it.lineno} 行）扩展解析与分派逻辑；"
            f"如存在调用链入口（CLI/管线），同步更新其输入校验与参数说明。\n"
        )

        reasoning_trace = [
            {
                "step": 1,
                "goal": "确认当前组件职责与边界",
                "evidence_ref": [it.rel_path],
                "intermediate_conclusion": f"`{it.name}` 在 `{it.rel_path}` 中承担特定处理职责，应在其边界内扩展。"
            },
            {
                "step": 2,
                "goal": "提出兼容性优先的扩展策略",
                "evidence_ref": [it.rel_path],
                "intermediate_conclusion": "通过适配层/解析函数新增支持，避免破坏现有契约与调用链。"
            }
        ]

        sample = {
            "id": f"design_auto_{idx:04d}",
            "task_type": "design",
            "instruction": instruction,
            "context": self._context_for_item(it),
            "reasoning_trace": reasoning_trace,
            "output": output,
            "metadata": {
                "repo": "OasisLMF",
                "business_stage": it.business_stage,
                "question_id": "AUTO_DESIGN",
                "difficulty": "medium",
                "language": "zh"
            }
        }
        TrainingSample.model_validate(sample)
        return sample

    def generate(self, n_qa: int, n_design: int):
        # 基于 docstring 的项里再挑：QA 优先函数/类都可以；Design 优先 class
        candidates = list(self.items)
        self.rng.shuffle(candidates)

        classes = [x for x in candidates if x.node_type == "class"]
        funcs = [x for x in candidates if x.node_type == "function"]

        qa_pool = candidates
        design_pool = classes if len(classes) >= n_design else candidates

        qa_samples = [self.create_fact_qa(it, i+1) for i, it in enumerate(qa_pool[:n_qa])]
        design_samples = [self.create_design(it, i+1) for i, it in enumerate(design_pool[:n_design])]

        return qa_samples + design_samples

def split_dataset(samples: List[dict], seed: int = 42):
    rng = random.Random(seed)
    rng.shuffle(samples)
    n = len(samples)
    n_train = int(n * 0.8)
    n_dev = int(n * 0.1)
    train = samples[:n_train]
    dev = samples[n_train:n_train + n_dev]
    test = samples[n_train + n_dev:]
    return train, dev, test

def write_jsonl(samples: List[dict], out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

def main():
    if not REPO_PATH.exists():
        raise FileNotFoundError(
            f"Repo path not found: {REPO_PATH}. Please clone/unzip OasisLMF into data/raw_repo/."
        )

    analyzer = CodeAnalyzer(REPO_PATH)
    analyzer.scan()

    if not analyzer.items:
        raise RuntimeError("No valid code items extracted. Check repo content or filters/docstrings.")

    gen = DatasetGenerator(analyzer.items, seed=SEED)
    samples = gen.generate(N_QA, N_DESIGN)

    # 再次全量校验（生成时已校验，这里作为最终保险）
    for s in samples:
        TrainingSample.model_validate(s)

    train, dev, test = split_dataset(samples, seed=SEED)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(train, OUT_DIR / "train.jsonl")
    write_jsonl(dev, OUT_DIR / "dev.jsonl")
    write_jsonl(test, OUT_DIR / "test.jsonl")

    print(f"✅ Done. total={len(samples)} train={len(train)} dev={len(dev)} test={len(test)}")
    print(f"Output dir: {OUT_DIR.resolve()}")

if __name__ == "__main__":
    main()
