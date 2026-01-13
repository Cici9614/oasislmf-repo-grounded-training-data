import ast
import json
import os
from dataclasses import dataclass, asdict
from glob import glob
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ===================== Path Config (Windows/PyCharm friendly) =====================
ROOT = Path(__file__).resolve().parents[2]  # project root
REPO_PATH = ROOT / "data" / "raw_repo"
OUT_DIR = ROOT / "data" / "intermediate"
CATALOG_PATH = OUT_DIR / "catalog.json"
STATS_PATH = OUT_DIR / "catalog_stats.json"

MAX_SNIPPET_LINES = 80

SKIP_DIR_KEYWORDS = ("venv", ".venv", "__pycache__", ".tox", "site-packages", "dist-packages")
SKIP_FILE_KEYWORDS = ("test", "tests")


# ===================== Helpers =====================
def should_skip_file(path: str) -> bool:
    lp = path.lower()
    if any(k in lp for k in SKIP_DIR_KEYWORDS):
        return True
    base = os.path.basename(lp)
    if any(k in base for k in SKIP_FILE_KEYWORDS):
        return True
    return False


def safe_read_text(fp: Path) -> Optional[str]:
    try:
        return fp.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return fp.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None
    except Exception:
        return None


def detect_stage(rel_path: str) -> str:
    """
    Lightweight, explainable heuristic mapping file path -> business stage.
    v0: good enough to support coverage stats; can be replaced by a richer catalog later.
    """
    p = rel_path.lower()
    if any(k in p for k in ("exposure", "oed", "location", "expos")):
        return "exposure"
    if any(k in p for k in ("hazard", "peril", "event", "occurrence")):
        return "hazard"
    if any(k in p for k in ("gul", "loss", "groundup", "damage")):
        return "gul"
    if any(k in p for k in ("fm", "financial", "terms", "reinsurance", "profile")):
        return "fm"
    if any(k in p for k in ("aggregation", "aggre", "summary", "report", "reports")):
        return "aggregation"
    return "other"


def extract_snippet(lines: List[str], lineno: int, end_lineno: int) -> str:
    start = max(lineno - 1, 0)
    end = min(end_lineno, len(lines))
    if end - start > MAX_SNIPPET_LINES:
        end = start + MAX_SNIPPET_LINES
    return "".join(lines[start:end]).rstrip()


def chunk_id(rel_path: str, name: str, lineno: int) -> str:
    # stable + human-readable id (no hashing to keep it simple for homework)
    # Example: oasislmf/utils/profiles.py::foo@44
    return f"{rel_path}::{name}@{lineno}"


# ===================== Data Model =====================
@dataclass
class Chunk:
    chunk_id: str
    source_type: str          # "code"
    path: str                 # repo-relative path
    symbol_type: str          # "class" | "function"
    name: str
    lineno: int
    end_lineno: int
    business_stage: str       # exposure/hazard/gul/fm/aggregation/other
    docstring: str
    content: str              # snippet + docstring excerpt


# ===================== Analyzer =====================
class CatalogBuilder:
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.chunks: List[Chunk] = []
        self.parse_errors: List[Tuple[str, str]] = []

    def scan(self) -> None:
        pattern = str(self.repo_path / "**" / "*.py")
        files = glob(pattern, recursive=True)
        files = [f for f in files if not should_skip_file(f)]

        print(f"Scanning repo: {self.repo_path.resolve()}")
        print(f"Found {len(files)} python files (after filtering).")

        for f in files:
            self._parse_file(Path(f))

        print(f"✅ Catalog build done. chunks={len(self.chunks)} parse_errors={len(self.parse_errors)}")

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
        stage = detect_stage(rel_path)

        for node in ast.walk(tree):
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                continue

            name = getattr(node, "name", "")
            if not name or name.startswith("_"):
                continue

            doc = ast.get_docstring(node)
            if not doc or len(doc.strip()) < 10:
                continue

            lineno = getattr(node, "lineno", 1)
            end_lineno = getattr(node, "end_lineno", lineno)
            snip = extract_snippet(lines, lineno, end_lineno)

            node_type = "class" if isinstance(node, ast.ClassDef) else "function"
            cid = chunk_id(rel_path, name, lineno)

            assembled = (
                f"# File: {rel_path}\n"
                f"# {node_type}: {name} (lines {lineno}-{end_lineno})\n\n"
                f"{snip}\n\n"
                f'"""Docstring (excerpt)"""\n{doc.strip()}\n'
            ).strip()

            self.chunks.append(
                Chunk(
                    chunk_id=cid,
                    source_type="code",
                    path=rel_path,
                    symbol_type=node_type,
                    name=name,
                    lineno=lineno,
                    end_lineno=end_lineno,
                    business_stage=stage,
                    docstring=doc.strip(),
                    content=assembled,
                )
            )


# ===================== Output =====================
def build_stats(chunks: List[Chunk]) -> Dict:
    stage_count: Dict[str, int] = {}
    type_count: Dict[str, int] = {}
    stage_type_count: Dict[str, Dict[str, int]] = {}

    for c in chunks:
        stage_count[c.business_stage] = stage_count.get(c.business_stage, 0) + 1
        type_count[c.symbol_type] = type_count.get(c.symbol_type, 0) + 1

        if c.business_stage not in stage_type_count:
            stage_type_count[c.business_stage] = {}
        stage_type_count[c.business_stage][c.symbol_type] = stage_type_count[c.business_stage].get(c.symbol_type, 0) + 1

    return {
        "total_chunks": len(chunks),
        "by_business_stage": dict(sorted(stage_count.items(), key=lambda x: (-x[1], x[0]))),
        "by_symbol_type": dict(sorted(type_count.items(), key=lambda x: (-x[1], x[0]))),
        "by_stage_and_type": stage_type_count,
    }


def main() -> None:
    if not REPO_PATH.exists():
        raise FileNotFoundError(
            f"Repo path not found: {REPO_PATH}. Please clone/unzip OasisLMF into data/raw_repo/."
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    builder = CatalogBuilder(REPO_PATH)
    builder.scan()

    # Write catalog.json
    catalog_obj = {
        "repo": "OasisLMF",
        "repo_path": str(REPO_PATH.resolve()),
        "source": "AST scan (public class/function with docstring)",
        "max_snippet_lines": MAX_SNIPPET_LINES,
        "chunks": [asdict(c) for c in builder.chunks],
        "parse_errors": builder.parse_errors[:200],  # cap to keep file small
    }
    CATALOG_PATH.write_text(json.dumps(catalog_obj, ensure_ascii=False, indent=2), encoding="utf-8")

    # Write stats
    stats_obj = build_stats(builder.chunks)
    STATS_PATH.write_text(json.dumps(stats_obj, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ Wrote: {CATALOG_PATH.resolve()}")
    print(f"✅ Wrote: {STATS_PATH.resolve()}")


if __name__ == "__main__":
    main()
