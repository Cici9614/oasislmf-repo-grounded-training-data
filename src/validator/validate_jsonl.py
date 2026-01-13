#!/usr/bin/env python
# coding: utf-8

import argparse
import json
from pathlib import Path
from src.validator.sample_schema import TrainingSample

def validate_jsonl(path: str) -> None:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")

    bad = 0
    total = 0
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        total += 1
        try:
            obj = json.loads(line)
            TrainingSample.model_validate(obj)
        except Exception as e:
            bad += 1
            print(f"[Invalid] line {i}: {e}")

    if bad == 0:
        print(f"✅ All samples are valid. total={total}")
    else:
        print(f"❌ {bad} invalid samples found. total={total}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True, help="Path to a JSONL file")
    args = ap.parse_args()
    validate_jsonl(args.path)
