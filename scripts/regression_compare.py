#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


MetricSpec = tuple[str, str, str, float]


METRICS: list[MetricSpec] = [
    ("structure", "edge_iou", "higher", 0.005),
    ("structure", "line_iou", "higher", 0.005),
    ("structure", "dark_text_iou", "higher", 0.01),
    ("structure", "missing_structure_ratio", "lower", 0.005),
    ("structure", "extra_structure_ratio", "lower", 0.005),
    ("pixel", "mean_abs_diff", "lower", 0.25),
    ("pixel", "pixels_over_48", "lower", 0.0025),
]


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def get_metric(metrics: dict[str, Any], section: str, key: str) -> float:
    value = metrics.get(section, {}).get(key)
    if not isinstance(value, (int, float)):
        raise KeyError(f"missing numeric metric: {section}.{key}")
    return float(value)


def judge_delta(delta: float, direction: str, tolerance: float) -> str:
    if direction == "higher":
        if delta < -tolerance:
            return "regressed"
        if delta > tolerance:
            return "improved"
    else:
        if delta > tolerance:
            return "regressed"
        if delta < -tolerance:
            return "improved"
    return "stable"


def compare(baseline: Path, candidate: Path, quality: Path | None = None) -> dict[str, Any]:
    base = read_json(baseline)
    cand = read_json(candidate)
    quality_data = read_json(quality) if quality else None

    rows = []
    regressions = []
    improvements = []
    for section, key, direction, tolerance in METRICS:
        base_value = get_metric(base, section, key)
        cand_value = get_metric(cand, section, key)
        delta = cand_value - base_value
        verdict = judge_delta(delta, direction, tolerance)
        row = {
            "metric": f"{section}.{key}",
            "direction": direction,
            "baseline": base_value,
            "candidate": cand_value,
            "delta": delta,
            "tolerance": tolerance,
            "verdict": verdict,
        }
        rows.append(row)
        if verdict == "regressed":
            regressions.append(row)
        elif verdict == "improved":
            improvements.append(row)

    quality_pass = True
    if quality_data is not None:
        quality_pass = bool(quality_data.get("pass"))

    return {
        "baseline": str(baseline),
        "candidate": str(candidate),
        "quality": str(quality) if quality else None,
        "quality_pass": quality_pass,
        "pass": quality_pass and not regressions,
        "regressions": regressions,
        "improvements": improvements,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare png2ppt visual audit metrics against a baseline run.")
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--quality", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--fail-on-regression", action="store_true")
    args = parser.parse_args()

    result = compare(args.baseline, args.candidate, args.quality)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    if args.fail_on_regression and not result["pass"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
