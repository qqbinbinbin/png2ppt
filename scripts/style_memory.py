#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def default_memory_path(profile_path: Path | None = None) -> Path:
    if profile_path is not None:
        for parent in profile_path.expanduser().resolve().parents:
            if parent.name == "png2ppt":
                return parent / "_shared" / "work" / "reports" / "style_memory.jsonl"
    return Path("png2ppt") / "_shared" / "work" / "reports" / "style_memory.jsonl"


def metric_summary(quality: dict | None, audit: dict | None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if quality:
        result["quality"] = {
            "pass": quality.get("pass"),
            "slides": quality.get("slides"),
            "total_shapes": quality.get("total_shapes"),
            "total_pictures": quality.get("total_pictures"),
            "total_text_shapes": quality.get("total_text_shapes"),
            "large_media_count": len(quality.get("large_media", [])),
        }
    if audit:
        result["audit"] = {
            "pass": audit.get("pass"),
            "failures": audit.get("failures", []),
            "edge_iou": audit.get("structure", {}).get("edge_iou"),
            "line_iou": audit.get("structure", {}).get("line_iou"),
            "blue_structure_iou": audit.get("structure", {}).get("blue_structure_iou"),
            "dark_text_iou": audit.get("structure", {}).get("dark_text_iou"),
            "missing_structure_ratio": audit.get("structure", {}).get("missing_structure_ratio"),
            "extra_structure_ratio": audit.get("structure", {}).get("extra_structure_ratio"),
            "mean_abs_diff": audit.get("pixel", {}).get("mean_abs_diff"),
            "pixels_over_48": audit.get("pixel", {}).get("pixels_over_48"),
        }
    return result


def profile_summary(profile: dict) -> dict[str, Any]:
    return {
        "source": profile.get("source"),
        "size": profile.get("size"),
        "background": profile.get("background"),
        "density": profile.get("density"),
        "palette": {
            "dominant_count": profile.get("palette", {}).get("dominant_count"),
            "entropy": profile.get("palette", {}).get("entropy"),
            "family_ratios": profile.get("palette", {}).get("family_ratios", {}),
            "foreground_colors": profile.get("palette", {}).get("foreground_colors", [])[:8],
        },
        "layout": {
            "horizontal_line_count": profile.get("layout", {}).get("horizontal_line_count"),
            "vertical_line_count": profile.get("layout", {}).get("vertical_line_count"),
            "content_block_count": profile.get("layout", {}).get("content_block_count"),
            "text_block_count": profile.get("layout", {}).get("text_block_count"),
        },
        "recommendation": profile.get("recommendation"),
        "vector_features": profile.get("vector_features", {}),
    }


def append_record(
    memory: Path,
    profile: dict,
    quality: dict | None,
    audit: dict | None,
    decision: str,
    improvement: str,
    final_pptx: Path | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    memory.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "profile": profile_summary(profile),
        "metrics": metric_summary(quality, audit),
        "decision": decision,
        "improvement": improvement,
        "final_pptx": str(final_pptx.expanduser().resolve()) if final_pptx else None,
        "tags": tags or [],
    }
    with memory.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return entry


def read_memory(memory: Path) -> list[dict[str, Any]]:
    if not memory.exists():
        return []
    records = []
    for line in memory.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def feature_distance(a: dict[str, float], b: dict[str, float]) -> float:
    keys = sorted(set(a) & set(b))
    if not keys:
        return math.inf
    total = 0.0
    for key in keys:
        total += (float(a[key]) - float(b[key])) ** 2
    return math.sqrt(total / len(keys))


def nearest_records(memory: Path, profile: dict, limit: int) -> list[dict[str, Any]]:
    target = profile.get("vector_features", {})
    scored = []
    for record in read_memory(memory):
        features = record.get("profile", {}).get("vector_features", {})
        distance = feature_distance(target, features)
        if math.isfinite(distance):
            scored.append((distance, record))
    scored.sort(key=lambda item: item[0])
    result = []
    for distance, record in scored[:limit]:
        result.append(
            {
                "distance": distance,
                "timestamp": record.get("timestamp"),
                "source": record.get("profile", {}).get("source"),
                "recommendation": record.get("profile", {}).get("recommendation", {}),
                "decision": record.get("decision"),
                "improvement": record.get("improvement"),
                "metrics": record.get("metrics", {}),
                "tags": record.get("tags", []),
                "final_pptx": record.get("final_pptx"),
            }
        )
    return result


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist and query png2ppt adaptive style memory.")
    sub = parser.add_subparsers(dest="command", required=True)

    append = sub.add_parser("append", help="Append a reconstruction run to style memory.")
    append.add_argument("--profile", required=True, type=Path)
    append.add_argument("--memory", type=Path)
    append.add_argument("--quality-json", type=Path)
    append.add_argument("--audit-json", type=Path)
    append.add_argument("--final-pptx", type=Path)
    append.add_argument("--decision", default="")
    append.add_argument("--improvement", default="")
    append.add_argument("--tag", action="append", default=[])

    nearest = sub.add_parser("nearest", help="Find similar previous profiles.")
    nearest.add_argument("--profile", required=True, type=Path)
    nearest.add_argument("--memory", type=Path)
    nearest.add_argument("--limit", type=int, default=5)

    show = sub.add_parser("list", help="List recent memory records.")
    show.add_argument("--memory", type=Path)
    show.add_argument("--limit", type=int, default=10)

    args = parser.parse_args()

    if args.command == "append":
        profile = load_json(args.profile)
        if profile is None:
            raise FileNotFoundError(args.profile)
        memory = args.memory or default_memory_path(args.profile)
        entry = append_record(
            memory,
            profile,
            quality=load_json(args.quality_json),
            audit=load_json(args.audit_json),
            decision=args.decision,
            improvement=args.improvement,
            final_pptx=args.final_pptx,
            tags=args.tag,
        )
        print_json({"memory": str(memory), "entry": entry})
    elif args.command == "nearest":
        profile = load_json(args.profile)
        if profile is None:
            raise FileNotFoundError(args.profile)
        memory = args.memory or default_memory_path(args.profile)
        print_json({"memory": str(memory), "nearest": nearest_records(memory, profile, args.limit)})
    elif args.command == "list":
        memory = args.memory or default_memory_path(None)
        records = read_memory(memory)
        print_json({"memory": str(memory), "records": records[-args.limit :]})


if __name__ == "__main__":
    main()
