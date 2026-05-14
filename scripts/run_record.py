#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path | None) -> dict | None:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def append_record(
    report: Path,
    source: Path,
    final_pptx: Path,
    quality: dict | None = None,
    audit: dict | None = None,
    decision: str = "",
    improvement: str = "",
) -> None:
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if report.exists():
        lines.append(report.read_text(encoding="utf-8").rstrip())
    else:
        lines.append("# png2ppt Run Record")

    lines.extend(
        [
            "",
            f"## {source.name}",
            "",
            f"- timestamp: `{datetime.now(timezone.utc).isoformat()}`",
            f"- source: `{source}`",
            f"- final_pptx: `{final_pptx}`",
        ]
    )
    if quality:
        lines.extend(
            [
                f"- quality_pass: `{quality.get('pass')}`",
                f"- slides: `{quality.get('slides')}`",
                f"- shapes: `{quality.get('total_shapes')}`",
                f"- pictures: `{quality.get('total_pictures')}`",
                f"- text_shapes: `{quality.get('total_text_shapes')}`",
                f"- large_media: `{len(quality.get('large_media', []))}`",
            ]
        )
    if audit:
        pixel = audit.get("pixel", {})
        structure = audit.get("structure", {})
        lines.extend(
            [
                f"- audit_pass: `{audit.get('pass')}`",
                f"- edge_iou: `{structure.get('edge_iou')}`",
                f"- blue_structure_iou: `{structure.get('blue_structure_iou')}`",
                f"- pixels_over_48: `{pixel.get('pixels_over_48')}`",
            ]
        )
    if decision:
        lines.append(f"- decision: {decision}")
    if improvement:
        lines.append(f"- skill_improvement: {improvement}")

    report.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(report)


def main() -> None:
    parser = argparse.ArgumentParser(description="Append a png2ppt run record.")
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--final-pptx", required=True, type=Path)
    parser.add_argument("--quality-json", type=Path)
    parser.add_argument("--audit-json", type=Path)
    parser.add_argument("--decision", default="")
    parser.add_argument("--improvement", default="")
    args = parser.parse_args()

    append_record(
        args.report,
        args.source,
        args.final_pptx,
        quality=load_json(args.quality_json),
        audit=load_json(args.audit_json),
        decision=args.decision,
        improvement=args.improvement,
    )


if __name__ == "__main__":
    main()
