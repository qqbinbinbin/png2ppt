#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw
from scipy import ndimage


def load_rgb(path: Path, size: tuple[int, int] | None = None) -> Image.Image:
    image = Image.open(path).convert("RGB")
    if size and image.size != size:
        image = image.resize(size, Image.Resampling.LANCZOS)
    return image


def grayscale_array(image: Image.Image) -> np.ndarray:
    arr = np.asarray(image).astype(np.float32)
    return 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]


def edge_map(gray: np.ndarray) -> np.ndarray:
    sx = ndimage.sobel(gray, axis=1, mode="reflect")
    sy = ndimage.sobel(gray, axis=0, mode="reflect")
    mag = np.hypot(sx, sy)
    threshold = max(18.0, float(np.percentile(mag, 82)))
    edges = mag > threshold
    edges = ndimage.binary_opening(edges, structure=np.ones((2, 2)))
    return edges


def line_maps(edges: np.ndarray, min_len: int = 35) -> tuple[np.ndarray, np.ndarray]:
    horizontal = np.zeros_like(edges, dtype=bool)
    vertical = np.zeros_like(edges, dtype=bool)
    h, w = edges.shape
    for y in range(h):
        xs = np.flatnonzero(edges[y])
        if xs.size == 0:
            continue
        starts = np.r_[0, np.flatnonzero(np.diff(xs) > 1) + 1]
        ends = np.r_[starts[1:], xs.size]
        for start, end in zip(starts, ends):
            if end - start >= min_len:
                horizontal[y, xs[start:end]] = True
    for x in range(w):
        ys = np.flatnonzero(edges[:, x])
        if ys.size == 0:
            continue
        starts = np.r_[0, np.flatnonzero(np.diff(ys) > 1) + 1]
        ends = np.r_[starts[1:], ys.size]
        for start, end in zip(starts, ends):
            if end - start >= min_len:
                vertical[ys[start:end], x] = True
    return horizontal, vertical


def mask_iou(a: np.ndarray, b: np.ndarray) -> float:
    union = np.logical_or(a, b).sum()
    if union == 0:
        return 1.0
    return float(np.logical_and(a, b).sum() / union)


def blue_structure_mask(image: Image.Image) -> np.ndarray:
    arr = np.asarray(image).astype(np.int16)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    # Corporate blue/gray-blue strokes and fills; excludes most black body text.
    blue = (b > g + 8) & (b > r + 18) & (b > 80) & (r < 235)
    dark_blue = (b > r + 10) & (g > r + 2) & (r < 80) & (b < 190)
    light_border = (b > r + 5) & (b > g + 3) & (r > 170) & (g > 180) & (b > 195)
    mask = blue | dark_blue | light_border
    return ndimage.binary_opening(mask, structure=np.ones((2, 2)))


def dark_text_mask(image: Image.Image) -> np.ndarray:
    arr = np.asarray(image).astype(np.int16)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    # Dark text/strokes. This intentionally includes dark blue headings.
    mask = (r < 95) & (g < 120) & (b < 165)
    return ndimage.binary_opening(mask, structure=np.ones((2, 2)))


def bbox_from_mask(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.where(mask)
    if xs.size == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def connected_boxes(mask: np.ndarray, min_area: int = 150) -> list[dict[str, int]]:
    labels, count = ndimage.label(mask)
    boxes: list[dict[str, int]] = []
    for idx in range(1, count + 1):
        item = labels == idx
        area = int(item.sum())
        if area < min_area:
            continue
        bbox = bbox_from_mask(item)
        if not bbox:
            continue
        x1, y1, x2, y2 = bbox
        boxes.append({"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1, "area": area})
    boxes.sort(key=lambda b: b["area"], reverse=True)
    return boxes


def make_heatmap(ref: Image.Image, cand: Image.Image, out: Path) -> None:
    diff = ImageChops.difference(ref, cand).convert("L")
    diff_arr = np.asarray(diff).astype(np.float32)
    scale = 255.0 / max(1.0, float(np.percentile(diff_arr, 98)))
    hot = np.clip(diff_arr * scale, 0, 255).astype(np.uint8)
    overlay = Image.new("RGBA", ref.size, (0, 0, 0, 0))
    overlay_arr = np.asarray(overlay).copy()
    overlay_arr[:, :, 0] = hot
    overlay_arr[:, :, 3] = np.clip(hot * 1.2, 0, 180).astype(np.uint8)
    blended = Image.alpha_composite(ref.convert("RGBA"), Image.fromarray(overlay_arr, "RGBA"))
    blended.save(out)


def make_edge_overlay(ref_edges: np.ndarray, cand_edges: np.ndarray, out: Path) -> None:
    h, w = ref_edges.shape
    arr = np.full((h, w, 4), 255, dtype=np.uint8)
    arr[:, :, 3] = 255
    arr[ref_edges] = (0, 98, 255, 255)
    arr[cand_edges] = (255, 45, 45, 255)
    arr[np.logical_and(ref_edges, cand_edges)] = (30, 160, 80, 255)
    Image.fromarray(arr, "RGBA").save(out)


def make_box_overlay(ref: Image.Image, ref_boxes: list[dict[str, int]], cand_boxes: list[dict[str, int]], out: Path) -> None:
    image = ref.convert("RGBA")
    draw = ImageDraw.Draw(image)
    for box in ref_boxes[:80]:
        draw.rectangle((box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"]), outline=(0, 98, 255, 180), width=2)
    for box in cand_boxes[:80]:
        draw.rectangle((box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"]), outline=(255, 45, 45, 180), width=2)
    image.save(out)


def audit(reference: Path, candidate: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    ref = load_rgb(reference)
    cand = load_rgb(candidate, ref.size)

    ref_arr = np.asarray(ref).astype(np.int16)
    cand_arr = np.asarray(cand).astype(np.int16)
    abs_diff = np.abs(ref_arr - cand_arr)
    gray_ref = grayscale_array(ref)
    gray_cand = grayscale_array(cand)
    ref_edges = edge_map(gray_ref)
    cand_edges = edge_map(gray_cand)
    ref_h, ref_v = line_maps(ref_edges)
    cand_h, cand_v = line_maps(cand_edges)
    ref_blue = blue_structure_mask(ref)
    cand_blue = blue_structure_mask(cand)
    ref_dark = dark_text_mask(ref)
    cand_dark = dark_text_mask(cand)

    ref_structure = ref_edges | ref_h | ref_v
    cand_structure = cand_edges | cand_h | cand_v
    missing = ref_structure & ~ndimage.binary_dilation(cand_structure, iterations=2)
    extra = cand_structure & ~ndimage.binary_dilation(ref_structure, iterations=2)

    ref_boxes = connected_boxes(ref_structure)
    cand_boxes = connected_boxes(cand_structure)

    make_heatmap(ref, cand, out_dir / "pixel_diff_heatmap.png")
    make_edge_overlay(ref_structure, cand_structure, out_dir / "edge_overlay_ref_blue_candidate_red.png")
    make_box_overlay(ref, ref_boxes, cand_boxes, out_dir / "structure_boxes_ref_blue_candidate_red.png")

    metrics = {
        "reference": str(reference),
        "candidate": str(candidate),
        "size": {"width": ref.size[0], "height": ref.size[1]},
        "pixel": {
            "mean_abs_diff": float(abs_diff.mean()),
            "p95_abs_diff": float(np.percentile(abs_diff, 95)),
            "pixels_over_24": float((abs_diff.max(axis=2) > 24).mean()),
            "pixels_over_48": float((abs_diff.max(axis=2) > 48).mean()),
        },
        "structure": {
            "edge_iou": mask_iou(ref_edges, cand_edges),
            "line_iou": mask_iou(ref_h | ref_v, cand_h | cand_v),
            "blue_structure_iou": mask_iou(ref_blue, cand_blue),
            "dark_text_iou": mask_iou(ref_dark, cand_dark),
            "missing_structure_ratio": float(missing.sum() / max(1, ref_structure.sum())),
            "extra_structure_ratio": float(extra.sum() / max(1, cand_structure.sum())),
            "ref_box_count": len(ref_boxes),
            "candidate_box_count": len(cand_boxes),
        },
        "outputs": {
            "pixel_diff_heatmap": str(out_dir / "pixel_diff_heatmap.png"),
            "edge_overlay": str(out_dir / "edge_overlay_ref_blue_candidate_red.png"),
            "structure_boxes": str(out_dir / "structure_boxes_ref_blue_candidate_red.png"),
        },
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit visual fidelity between a reference slide image and candidate render.")
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--min-edge-iou", type=float, default=0.88)
    parser.add_argument("--min-line-iou", type=float, default=0.88)
    parser.add_argument("--max-missing-structure", type=float, default=0.04)
    parser.add_argument("--max-extra-structure", type=float, default=0.04)
    parser.add_argument("--max-pixels-over-48", type=float, default=0.03)
    parser.add_argument("--fail-on-threshold", action="store_true")
    args = parser.parse_args()
    metrics = audit(args.reference, args.candidate, args.out_dir)
    thresholds = {
        "min_edge_iou": args.min_edge_iou,
        "min_line_iou": args.min_line_iou,
        "max_missing_structure": args.max_missing_structure,
        "max_extra_structure": args.max_extra_structure,
        "max_pixels_over_48": args.max_pixels_over_48,
    }
    failures = []
    if metrics["structure"]["edge_iou"] < args.min_edge_iou:
        failures.append("edge_iou")
    if metrics["structure"]["line_iou"] < args.min_line_iou:
        failures.append("line_iou")
    if metrics["structure"]["missing_structure_ratio"] > args.max_missing_structure:
        failures.append("missing_structure_ratio")
    if metrics["structure"]["extra_structure_ratio"] > args.max_extra_structure:
        failures.append("extra_structure_ratio")
    if metrics["pixel"]["pixels_over_48"] > args.max_pixels_over_48:
        failures.append("pixels_over_48")
    metrics["thresholds"] = thresholds
    metrics["pass"] = not failures
    metrics["failures"] = failures
    (args.out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    if failures and args.fail_on_threshold:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
