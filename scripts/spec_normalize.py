#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


BOX_KEYS = ("x", "y", "w", "h")
LINE_KEYS = ("x1", "y1", "x2", "y2")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def snap_value(value: Any, grid: float) -> Any:
    if not isinstance(value, (int, float)) or grid <= 0:
        return value
    return round(value / grid) * grid


def snap_geometry(obj: Any, grid: float) -> None:
    if isinstance(obj, dict):
        if all(key in obj for key in BOX_KEYS):
            for key in BOX_KEYS:
                obj[key] = snap_value(obj[key], grid)
        if all(key in obj for key in LINE_KEYS):
            for key in LINE_KEYS:
                obj[key] = snap_value(obj[key], grid)
        if "stroke_width" in obj and isinstance(obj["stroke_width"], (int, float)):
            obj["stroke_width"] = round(obj["stroke_width"] * 2) / 2
        if "radius" in obj and isinstance(obj["radius"], (int, float)):
            obj["radius"] = snap_value(obj["radius"], max(1, grid / 2))
        for value in obj.values():
            snap_geometry(value, grid)
    elif isinstance(obj, list):
        for item in obj:
            snap_geometry(item, grid)


def collect_named_boxes(items: Any) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    if isinstance(items, dict):
        if all(key in items for key in BOX_KEYS):
            kind = str(items.get("component_type") or items.get("type") or items.get("role") or "")
            if kind:
                groups.setdefault(kind, []).append(items)
        for value in items.values():
            for key, boxes in collect_named_boxes(value).items():
                groups.setdefault(key, []).extend(boxes)
    elif isinstance(items, list):
        for item in items:
            for key, boxes in collect_named_boxes(item).items():
                groups.setdefault(key, []).extend(boxes)
    return groups


def normalize_repeated_boxes(spec: dict[str, Any], tolerance: float) -> list[str]:
    notes: list[str] = []
    groups = collect_named_boxes(spec)
    for kind, boxes in groups.items():
        if len(boxes) < 3:
            continue
        widths = [box["w"] for box in boxes if isinstance(box.get("w"), (int, float))]
        heights = [box["h"] for box in boxes if isinstance(box.get("h"), (int, float))]
        if len(widths) == len(boxes) and max(widths) - min(widths) <= tolerance:
            target = round(sum(widths) / len(widths), 1)
            for box in boxes:
                box["w"] = target
            notes.append(f"Normalized repeated `{kind}` widths to {target}.")
        if len(heights) == len(boxes) and max(heights) - min(heights) <= tolerance:
            target = round(sum(heights) / len(heights), 1)
            for box in boxes:
                box["h"] = target
            notes.append(f"Normalized repeated `{kind}` heights to {target}.")
    return notes


def enforce_icon_policy(spec: dict[str, Any], mode: str) -> list[str]:
    notes: list[str] = []
    if mode not in {"semantic_png", "semantic_svg", "native_symbol", "preserve"}:
        raise ValueError(f"Unsupported icon mode: {mode}")
    if mode == "preserve":
        return notes

    def visit(obj: Any) -> None:
        if isinstance(obj, dict):
            kind = str(obj.get("component_type") or obj.get("type") or obj.get("role") or "").lower()
            if "icon" in kind or obj.get("icon"):
                old = obj.get("editability")
                obj["icon_policy"] = mode
                if old in {None, "", "editable"}:
                    obj["editability"] = "semantic_asset"
            for value in obj.values():
                visit(value)
        elif isinstance(obj, list):
            for item in obj:
                visit(item)

    visit(spec)
    notes.append(f"Applied `{mode}` icon policy to icon-like components.")
    return notes


def ensure_metadata(spec: dict[str, Any], strategy: str, notes: list[str]) -> None:
    meta = spec.setdefault("normalization", {})
    meta["strategy"] = strategy
    existing = meta.get("intentional_normalization", [])
    if not isinstance(existing, list):
        existing = [str(existing)]
    meta["intentional_normalization"] = existing + notes
    meta.setdefault("semantic_gate", "Preserve title, conclusion, reading order, page type, and management argument.")
    meta.setdefault("structural_gate", "Preserve major regions, cards, tables, connectors, badges, footer, and visual hierarchy.")


def normalize_spec(
    spec: dict[str, Any],
    grid: float,
    repeated_tolerance: float,
    icon_mode: str,
    strategy: str,
) -> dict[str, Any]:
    result = deepcopy(spec)
    notes: list[str] = []
    if grid > 0:
        snap_geometry(result, grid)
        notes.append(f"Snapped native geometry to a {grid:g}px grid.")
    if repeated_tolerance > 0:
        notes.extend(normalize_repeated_boxes(result, repeated_tolerance))
    notes.extend(enforce_icon_policy(result, icon_mode))
    ensure_metadata(result, strategy, notes)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize a png2ppt component spec using a forward design-system pass."
    )
    parser.add_argument("input", type=Path, help="Input component spec JSON.")
    parser.add_argument("--out", required=True, type=Path, help="Output normalized spec JSON.")
    parser.add_argument("--grid", type=float, default=4, help="Pixel grid for snapping coordinates.")
    parser.add_argument(
        "--repeated-tolerance",
        type=float,
        default=8,
        help="Max width/height spread for normalizing repeated component groups.",
    )
    parser.add_argument(
        "--icon-mode",
        default="semantic_png",
        choices=["semantic_png", "semantic_svg", "native_symbol", "preserve"],
        help="Icon editability/asset strategy.",
    )
    parser.add_argument(
        "--strategy",
        default="reverse_extract_then_forward_normalize",
        help="Strategy name recorded in the normalized spec.",
    )
    args = parser.parse_args()

    normalized = normalize_spec(
        load_json(args.input),
        grid=args.grid,
        repeated_tolerance=args.repeated_tolerance,
        icon_mode=args.icon_mode,
        strategy=args.strategy,
    )
    write_json(args.out, normalized)
    print(args.out)


if __name__ == "__main__":
    main()
