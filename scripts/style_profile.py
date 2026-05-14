#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


def load_rgb(path: Path) -> Image.Image:
    image = Image.open(path)
    if image.mode in {"RGBA", "LA"}:
        base = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(base, image.convert("RGBA"))
    return image.convert("RGB")


def rgb_hex(rgb: tuple[int, int, int] | np.ndarray) -> str:
    r, g, b = [int(v) for v in rgb]
    return f"#{r:02X}{g:02X}{b:02X}"


def luminance(arr: np.ndarray) -> np.ndarray:
    return 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]


def background_from_border(arr: np.ndarray) -> dict:
    h, w, _ = arr.shape
    pad_x = max(4, int(w * 0.025))
    pad_y = max(4, int(h * 0.025))
    border = np.concatenate(
        [
            arr[:pad_y, :, :].reshape(-1, 3),
            arr[h - pad_y :, :, :].reshape(-1, 3),
            arr[:, :pad_x, :].reshape(-1, 3),
            arr[:, w - pad_x :, :].reshape(-1, 3),
        ],
        axis=0,
    )
    median = np.median(border, axis=0)
    mean = np.mean(border, axis=0)
    luma = float(luminance(median).item())
    variability = float(np.mean(np.linalg.norm(border.astype(float) - median, axis=1)))
    return {
        "rgb": [int(round(v)) for v in median],
        "hex": rgb_hex(median),
        "mean_hex": rgb_hex(np.clip(mean, 0, 255)),
        "luminance": luma,
        "is_light": luma >= 190,
        "is_dark": luma <= 85,
        "border_variability": variability,
    }


def non_background_mask(arr: np.ndarray, background: dict) -> np.ndarray:
    bg = np.asarray(background["rgb"], dtype=np.float32)
    arr_f = arr.astype(np.float32)
    dist = np.linalg.norm(arr_f - bg, axis=2)
    gray = luminance(arr_f)
    mx = arr_f.max(axis=2)
    mn = arr_f.min(axis=2)
    sat = mx - mn
    threshold = max(18.0, min(45.0, background["border_variability"] * 1.8 + 14.0))
    color_shift = dist > threshold
    dark_shift = np.abs(gray - background["luminance"]) > 22
    saturated_shift = (sat > 28) & (dist > threshold * 0.65)
    mask = color_shift | dark_shift | saturated_shift
    mask = ndimage.binary_opening(mask, structure=np.ones((2, 2)))
    mask = ndimage.binary_closing(mask, structure=np.ones((2, 2)))
    return mask


def bbox_from_mask(mask: np.ndarray) -> dict | None:
    ys, xs = np.where(mask)
    if xs.size == 0:
        return None
    x1, y1, x2, y2 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    return {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1}


def edge_map(gray: np.ndarray) -> np.ndarray:
    sx = ndimage.sobel(gray, axis=1, mode="reflect")
    sy = ndimage.sobel(gray, axis=0, mode="reflect")
    mag = np.hypot(sx, sy)
    threshold = max(16.0, float(np.percentile(mag, 84)))
    edges = mag > threshold
    edges = ndimage.binary_opening(edges, structure=np.ones((2, 2)))
    return edges


def axis_line_candidates(edges: np.ndarray, axis: str, min_len: int) -> list[dict]:
    if axis == "horizontal":
        closed = ndimage.binary_closing(edges, structure=np.ones((1, 7)))
        line_map = ndimage.binary_opening(closed, structure=np.ones((1, max(3, min_len // 2))))
        counts = line_map.sum(axis=1)
        rows = np.flatnonzero(counts >= min_len)
        return _candidate_groups(line_map, rows, "horizontal")
    if axis == "vertical":
        closed = ndimage.binary_closing(edges, structure=np.ones((7, 1)))
        line_map = ndimage.binary_opening(closed, structure=np.ones((max(3, min_len // 2), 1)))
        counts = line_map.sum(axis=0)
        cols = np.flatnonzero(counts >= min_len)
        return _candidate_groups(line_map, cols, "vertical")
    raise ValueError(axis)


def _candidate_groups(line_map: np.ndarray, indexes: np.ndarray, axis: str) -> list[dict]:
    if indexes.size == 0:
        return []
    starts = np.r_[0, np.flatnonzero(np.diff(indexes) > 1) + 1]
    ends = np.r_[starts[1:], indexes.size]
    candidates: list[dict] = []
    for start, end in zip(starts, ends):
        group = indexes[start:end]
        if axis == "horizontal":
            rows = line_map[group, :]
            ys, xs = np.where(rows)
            if xs.size == 0:
                continue
            y = int(round(float(group.mean())))
            candidates.append(
                {
                    "x": int(xs.min()),
                    "y": y,
                    "w": int(xs.max() - xs.min() + 1),
                    "h": int(group[-1] - group[0] + 1),
                }
            )
        else:
            cols = line_map[:, group]
            ys, xs = np.where(cols)
            if ys.size == 0:
                continue
            x = int(round(float(group.mean())))
            candidates.append(
                {
                    "x": x,
                    "y": int(ys.min()),
                    "w": int(group[-1] - group[0] + 1),
                    "h": int(ys.max() - ys.min() + 1),
                }
            )
    candidates.sort(key=lambda item: item["w"] * item["h"], reverse=True)
    return candidates


def connected_boxes(mask: np.ndarray, min_area: int, max_boxes: int = 80) -> list[dict]:
    labels, count = ndimage.label(mask)
    boxes: list[dict] = []
    for idx in range(1, count + 1):
        item = labels == idx
        area = int(item.sum())
        if area < min_area:
            continue
        bbox = bbox_from_mask(item)
        if not bbox:
            continue
        bbox["area"] = area
        bbox["area_ratio"] = area / mask.size
        boxes.append(bbox)
    boxes.sort(key=lambda b: b["area"], reverse=True)
    return boxes[:max_boxes]


def downsample_array(image: Image.Image, max_side: int = 360) -> np.ndarray:
    small = image.copy()
    small.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return np.asarray(small.convert("RGB"))


def dominant_colors(arr: np.ndarray, mask: np.ndarray | None = None, limit: int = 10) -> list[dict]:
    pixels = arr.reshape(-1, 3)
    if mask is not None:
        flat_mask = mask.reshape(-1)
        pixels = pixels[flat_mask]
    if pixels.size == 0:
        return []
    quantized = (pixels // 16) * 16 + 8
    counts = Counter(map(tuple, quantized.tolist()))
    total = sum(counts.values())
    result = []
    for rgb, count in counts.most_common(limit):
        result.append({"hex": rgb_hex(rgb), "rgb": list(map(int, rgb)), "ratio": count / total})
    return result


def color_family_ratios(arr: np.ndarray, mask: np.ndarray) -> dict[str, float]:
    pixels = arr[mask]
    if pixels.size == 0:
        return {}
    pixels = pixels.astype(np.float32) / 255.0
    r, g, b = pixels[:, 0], pixels[:, 1], pixels[:, 2]
    mx = pixels.max(axis=1)
    mn = pixels.min(axis=1)
    delta = mx - mn
    sat = np.divide(delta, mx, out=np.zeros_like(delta), where=mx > 0)
    hue = np.zeros_like(mx)
    nonzero = delta > 1e-6
    red_max = nonzero & (mx == r)
    green_max = nonzero & (mx == g)
    blue_max = nonzero & (mx == b)
    hue[red_max] = ((g[red_max] - b[red_max]) / delta[red_max]) % 6
    hue[green_max] = (b[green_max] - r[green_max]) / delta[green_max] + 2
    hue[blue_max] = (r[blue_max] - g[blue_max]) / delta[blue_max] + 4
    hue = hue * 60
    neutral = sat < 0.12
    families = {
        "neutral": neutral,
        "red": (~neutral) & ((hue < 20) | (hue >= 340)),
        "orange": (~neutral) & (hue >= 20) & (hue < 55),
        "yellow": (~neutral) & (hue >= 55) & (hue < 80),
        "green": (~neutral) & (hue >= 80) & (hue < 165),
        "teal": (~neutral) & (hue >= 165) & (hue < 205),
        "blue": (~neutral) & (hue >= 205) & (hue < 260),
        "purple": (~neutral) & (hue >= 260) & (hue < 310),
        "pink": (~neutral) & (hue >= 310) & (hue < 340),
    }
    total = len(pixels)
    return {name: float(values.sum() / total) for name, values in families.items()}


def entropy_from_colors(colors: list[dict]) -> float:
    if not colors:
        return 0.0
    entropy = -sum(item["ratio"] * math.log2(max(item["ratio"], 1e-9)) for item in colors)
    return float(entropy)


def classify_style_family(metrics: dict) -> dict:
    size = metrics["size"]
    density = metrics["density"]
    palette = metrics["palette"]
    layout = metrics["layout"]
    background = metrics["background"]
    family = palette.get("family_ratios", {})

    line_count = layout["horizontal_line_count"] + layout["vertical_line_count"]
    aspect = size["aspect_ratio"]
    blue_ratio = family.get("blue", 0.0)
    neutral_ratio = family.get("neutral", 0.0)
    consulting_signals = [
        background.get("is_light"),
        1.70 <= aspect <= 1.85,
        density["content_area_ratio"] >= 0.88,
        0.12 <= density["edge_density"] <= 0.20,
        density["line_density"] >= 2.8,
        density["non_background_ratio"] >= 0.16,
        density["dark_ratio"] >= 0.12,
        blue_ratio >= 0.55,
        neutral_ratio <= 0.35,
        line_count >= 45,
        layout["content_block_count"] >= 35,
        layout["text_block_count"] >= 90,
    ]
    consulting_score = sum(1 for item in consulting_signals if item) / len(consulting_signals)
    if consulting_score >= 0.75:
        return {
            "name": "consulting_blueprint",
            "confidence": round(consulting_score, 3),
            "reason": "light 16:9 consulting slide with dense blue structural layout, many lines/cards, and high text density",
            "tokens": [
                "white canvas",
                "deep-blue titles and section badges",
                "light-blue cards and table rows",
                "dense separators, arrows, and numbered steps",
                "footer conclusion/output strip",
            ],
        }

    if background.get("is_dark") and palette["entropy"] >= 2.2 and density["edge_density"] >= 0.10:
        return {
            "name": "dark_technical",
            "confidence": 0.7,
            "reason": "dark structured page with textured/high-entropy foreground",
            "tokens": ["dark background", "muted text", "technical cards", "glow or texture"],
        }

    if background.get("is_light") and line_count >= 8 and layout["content_block_count"] >= 10:
        return {
            "name": "structured_corporate",
            "confidence": 0.6,
            "reason": "light structured corporate slide with editable geometry",
            "tokens": ["light canvas", "structured panels", "rules", "cards"],
        }

    return {
        "name": "general",
        "confidence": 0.4,
        "reason": "no strong reusable style-family signal detected",
        "tokens": [],
    }


def recommend_strategy(metrics: dict) -> dict:
    density = metrics["density"]
    palette = metrics["palette"]
    layout = metrics["layout"]
    background = metrics["background"]
    colors = palette["dominant_count"]
    edge_density = density["edge_density"]
    non_bg = density["non_background_ratio"]
    line_count = layout["horizontal_line_count"] + layout["vertical_line_count"]
    block_count = layout["content_block_count"]
    entropy = palette["entropy"]
    family = palette.get("family_ratios", {})
    style_family = metrics.get("style_family") or classify_style_family(metrics)

    if style_family["name"] == "consulting_blueprint":
        primary = "consulting_blueprint_hybrid_reconstruction"
        reason = "consulting blueprint slide: preserve grid, cards, arrows, badges, table rows, and footer strips as editable geometry; keep icons and decorative skyline assets as PNG"
        editable_priority = "high"
    elif background.get("is_dark") and entropy >= 2.2 and edge_density >= 0.10 and family.get("neutral", 0) >= 0.35:
        primary = "texture_backed_hybrid_reconstruction"
        reason = "dark textured structured page; editable overlay should be combined with a low-opacity/cropped texture or background layer"
        editable_priority = "medium_high"
    elif colors >= 9 and entropy >= 2.4 and edge_density < 0.055:
        primary = "fidelity_png_placement"
        reason = "many colors with low structural edge density suggests photo/illustration-like content"
        editable_priority = "low"
    elif line_count >= 8 or block_count >= 10 or edge_density >= 0.07:
        primary = "native_or_hybrid_reconstruction"
        reason = "structured content with many lines/blocks is a good candidate for editable geometry"
        editable_priority = "high"
    elif non_bg < 0.035 and line_count < 4:
        primary = "simple_native_reconstruction"
        reason = "sparse page with few objects can be rebuilt with native PPT primitives"
        editable_priority = "medium"
    else:
        primary = "hybrid_reconstruction"
        reason = "mixed bitmap and structured content; rebuild layout and keep complex assets as PNG"
        editable_priority = "medium"

    return {
        "primary": primary,
        "editable_priority": editable_priority,
        "reason": reason,
        "style_family": style_family,
        "first_pass": [
            "lock source dimensions and output paths",
            "build a region/component spec before drawing",
            "render and audit candidate against the PNG",
            "record profile, metrics, decision, and next improvement",
        ],
    }


def profile_image(path: Path) -> dict:
    image = load_rgb(path)
    arr = np.asarray(image)
    h, w, _ = arr.shape
    background = background_from_border(arr)
    non_bg = non_background_mask(arr, background)
    gray = luminance(arr.astype(np.float32))
    edges = edge_map(gray)

    content_bbox = bbox_from_mask(non_bg)
    content_area_ratio = 0.0
    if content_bbox:
        content_area_ratio = (content_bbox["w"] * content_bbox["h"]) / (w * h)

    h_lines = axis_line_candidates(edges, "horizontal", max(36, int(w * 0.08)))
    v_lines = axis_line_candidates(edges, "vertical", max(28, int(h * 0.08)))

    block_mask = ndimage.binary_dilation(non_bg, structure=np.ones((5, 5)))
    block_mask = ndimage.binary_closing(block_mask, structure=np.ones((9, 9)))
    content_blocks = connected_boxes(block_mask, min_area=max(80, int(w * h * 0.00035)))

    dark_mask = (gray < 135) & non_bg
    text_like = ndimage.binary_dilation(dark_mask, structure=np.ones((2, 5)))
    text_blocks = connected_boxes(text_like, min_area=max(32, int(w * h * 0.00008)), max_boxes=120)

    small_arr = downsample_array(image)
    small_bg = background_from_border(small_arr)
    small_non_bg = non_background_mask(small_arr, small_bg)
    all_colors = dominant_colors(small_arr, limit=12)
    foreground_colors = dominant_colors(small_arr, small_non_bg, limit=12)
    family = color_family_ratios(small_arr, small_non_bg)

    mx = arr.max(axis=2).astype(np.float32)
    mn = arr.min(axis=2).astype(np.float32)
    saturation_mean = float(np.mean((mx - mn) / np.maximum(mx, 1.0)))
    line_density = float((len(h_lines) + len(v_lines)) / max(1, (w + h) / 100))
    edge_density = float(edges.mean())
    non_bg_ratio = float(non_bg.mean())
    dark_ratio = float(dark_mask.mean())

    metrics = {
        "source": str(path.expanduser().resolve()),
        "size": {"width": w, "height": h, "aspect_ratio": w / h},
        "background": background,
        "content_bbox": content_bbox,
        "density": {
            "non_background_ratio": non_bg_ratio,
            "content_area_ratio": content_area_ratio,
            "edge_density": edge_density,
            "line_density": line_density,
            "dark_ratio": dark_ratio,
            "saturation_mean": saturation_mean,
        },
        "palette": {
            "dominant_count": len(foreground_colors),
            "entropy": entropy_from_colors(foreground_colors),
            "dominant_colors": all_colors,
            "foreground_colors": foreground_colors,
            "family_ratios": family,
        },
        "layout": {
            "horizontal_line_count": len(h_lines),
            "vertical_line_count": len(v_lines),
            "content_block_count": len(content_blocks),
            "text_block_count": len(text_blocks),
            "horizontal_lines": h_lines[:40],
            "vertical_lines": v_lines[:40],
            "content_blocks": content_blocks[:40],
            "text_blocks": text_blocks[:40],
        },
    }
    metrics["style_family"] = classify_style_family(metrics)
    metrics["recommendation"] = recommend_strategy(metrics)
    metrics["vector_features"] = {
        "aspect_ratio_scaled": min(1.0, (w / h) / 4.0),
        "width_scaled": min(1.0, w / 4000.0),
        "height_scaled": min(1.0, h / 3000.0),
        "background_luma": background["luminance"] / 255.0,
        "background_variability": min(1.0, background["border_variability"] / 120.0),
        "non_background_ratio": non_bg_ratio,
        "content_area_ratio": content_area_ratio,
        "edge_density": edge_density,
        "line_density_scaled": min(1.0, line_density / 8.0),
        "dark_ratio": dark_ratio,
        "saturation_mean": saturation_mean,
        "palette_entropy_scaled": min(1.0, metrics["palette"]["entropy"] / 4.0),
        "horizontal_lines_scaled": min(1.0, len(h_lines) / 80.0),
        "vertical_lines_scaled": min(1.0, len(v_lines) / 80.0),
        "content_blocks_scaled": min(1.0, len(content_blocks) / 100.0),
        "text_blocks_scaled": min(1.0, len(text_blocks) / 150.0),
        "blue_family_ratio": family.get("blue", 0.0),
        "green_family_ratio": family.get("green", 0.0),
        "orange_family_ratio": family.get("orange", 0.0),
        "purple_family_ratio": family.get("purple", 0.0),
        "neutral_family_ratio": family.get("neutral", 0.0),
    }
    return metrics


def write_debug_masks(path: Path, profile: dict, out_dir: Path) -> None:
    image = load_rgb(path)
    arr = np.asarray(image)
    background = background_from_border(arr)
    non_bg = non_background_mask(arr, background)
    gray = luminance(arr.astype(np.float32))
    edges = edge_map(gray)
    out_dir.mkdir(parents=True, exist_ok=True)
    Image.fromarray((non_bg.astype(np.uint8) * 255), mode="L").save(out_dir / "non_background_mask.png")
    Image.fromarray((edges.astype(np.uint8) * 255), mode="L").save(out_dir / "edge_mask.png")
    (out_dir / "style_profile.debug.json").write_text(
        json.dumps({"source": profile["source"], "debug_dir": str(out_dir)}, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a style/layout profile for a PNG before PPT reconstruction.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--out", type=Path, help="Write profile JSON to this path.")
    parser.add_argument("--debug-dir", type=Path, help="Optional directory for masks used during diagnosis.")
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    if source.suffix.lower() != ".png":
        raise ValueError(f"Only PNG input is supported: {source}")
    profile = profile_image(source)
    text = json.dumps(profile, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    if args.debug_dir:
        write_debug_masks(source, profile, args.debug_dir)
    print(text)


if __name__ == "__main__":
    main()
