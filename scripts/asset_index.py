#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import time
import warnings
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

try:
    from PIL import Image, ImageStat
except ImportError:  # pragma: no cover
    Image = None
    ImageStat = None


SCHEMA_VERSION = "1.0.0"
EMU_PER_IN = 914400
NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


@dataclass(frozen=True)
class SourceInfo:
    source_id: str
    name: str
    path: Path
    sha256_16: str
    bytes: int
    privacy: str


def now_local() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def safe_slug(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._-")
    return slug or "deck"


def sha256_16_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def sha256_16_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def natural_slide_key(name: str) -> int:
    match = re.search(r"slides/slide(\d+)\.xml$", name)
    return int(match.group(1)) if match else 10**9


def read_xml(zf: zipfile.ZipFile, name: str) -> ET.Element | None:
    try:
        return ET.fromstring(zf.read(name))
    except Exception:
        return None


def base_record(record_type: str, source: SourceInfo) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": record_type,
        "source_id": source.source_id,
        "source_name": source.name,
        "source_sha256_16": source.sha256_16,
        "privacy": source.privacy,
    }


def local_media_path(target: str, slide_name: str) -> str:
    if target.startswith("../"):
        return "ppt/" + target[3:]
    if target.startswith("/"):
        return target.lstrip("/")
    if target.startswith("ppt/"):
        return target
    return str(Path(Path(slide_name).parent, target)).replace("\\", "/")


def rel_targets(zf: zipfile.ZipFile, slide_name: str) -> dict[str, dict[str, str]]:
    rel_name = slide_name.replace("slides/", "slides/_rels/") + ".rels"
    result: dict[str, dict[str, str]] = {}
    if rel_name not in zf.namelist():
        return result
    root = read_xml(zf, rel_name)
    if root is None:
        return result
    for rel in root:
        rid = rel.attrib.get("Id")
        target = rel.attrib.get("Target", "")
        rel_type = rel.attrib.get("Type", "").split("/")[-1]
        if rid:
            result[rid] = {
                "target": local_media_path(target, slide_name),
                "relationship_type": rel_type,
            }
    return result


def text_length(el: ET.Element) -> int:
    return sum(len(node.text or "") for node in el.findall(".//a:t", NS))


def name_hash(el: ET.Element) -> str | None:
    node = el.find(".//p:cNvPr", NS)
    name = node.attrib.get("name", "") if node is not None else ""
    return sha256_16_bytes(name.encode("utf-8")) if name else None


def shape_class(el: ET.Element) -> str:
    tag = el.tag.rsplit("}", 1)[-1]
    if tag == "sp":
        prst = el.find(".//a:prstGeom", NS)
        preset = prst.attrib.get("prst") if prst is not None else "shape"
        return f"{'text' if text_length(el) else 'shape'}_{preset}"
    if tag == "pic":
        return "picture"
    if tag == "graphicFrame":
        return "table" if el.find(".//a:tbl", NS) is not None else "graphic_frame"
    if tag == "cxnSp":
        prst = el.find(".//a:prstGeom", NS)
        preset = prst.attrib.get("prst") if prst is not None else "line"
        return f"connector_{preset}"
    if tag == "grpSp":
        return "group"
    return tag


def bbox_in(el: ET.Element) -> dict[str, float] | None:
    xfrm = el.find(".//a:xfrm", NS)
    if xfrm is None:
        return None
    off = xfrm.find("a:off", NS)
    ext = xfrm.find("a:ext", NS)
    if off is None or ext is None:
        return None
    try:
        return {
            "x": round(int(off.attrib.get("x", 0)) / EMU_PER_IN, 4),
            "y": round(int(off.attrib.get("y", 0)) / EMU_PER_IN, 4),
            "w": round(int(ext.attrib.get("cx", 0)) / EMU_PER_IN, 4),
            "h": round(int(ext.attrib.get("cy", 0)) / EMU_PER_IN, 4),
        }
    except ValueError:
        return None


def is_media_path(path: str) -> bool:
    return path.startswith("ppt/media/")


def shape_media_refs(el: ET.Element, rels: dict[str, dict[str, str]]) -> list[str]:
    refs = []
    seen = set()
    # PPTX SVG pictures often keep a PNG preview in a:blip and the SVG source in
    # an extension element. Scan relationship attributes generically so both are
    # indexable without needing to know every vendor namespace.
    for node in el.iter():
        for attr, rid in node.attrib.items():
            if not attr.endswith("}embed") and not attr.endswith("}link"):
                continue
            if rid not in rels:
                continue
            target = rels[rid]["target"]
            if target in seen or not is_media_path(target):
                continue
            seen.add(target)
            refs.append(target)
    return refs


def bbox_summary(boxes: list[dict[str, float]]) -> dict[str, Any]:
    if not boxes:
        return {"count": 0}
    areas = [max(0.0, box["w"]) * max(0.0, box["h"]) for box in boxes]
    widths = [box["w"] for box in boxes]
    heights = [box["h"] for box in boxes]
    return {
        "count": len(boxes),
        "area_sum": round(sum(areas), 4),
        "area_avg": round(sum(areas) / len(areas), 4),
        "x_min": round(min(box["x"] for box in boxes), 4),
        "y_min": round(min(box["y"] for box in boxes), 4),
        "x_max": round(max(box["x"] + box["w"] for box in boxes), 4),
        "y_max": round(max(box["y"] + box["h"] for box in boxes), 4),
        "w_median": round(statistics.median(widths), 4),
        "h_median": round(statistics.median(heights), 4),
    }


def slide_size_in(zf: zipfile.ZipFile) -> dict[str, float] | None:
    root = read_xml(zf, "ppt/presentation.xml")
    if root is None:
        return None
    node = root.find("p:sldSz", NS)
    if node is None:
        return None
    return {
        "width": round(int(node.attrib.get("cx", 0)) / EMU_PER_IN, 4),
        "height": round(int(node.attrib.get("cy", 0)) / EMU_PER_IN, 4),
    }


def dominant_colors(image: Any, max_colors: int = 5) -> list[str]:
    if Image is None:
        return []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        thumb = image.convert("RGBA").convert("RGB").resize((32, 32))
        colors = thumb.getcolors(maxcolors=1024) or []
    colors.sort(reverse=True)
    return ["#%02x%02x%02x" % rgb for _count, rgb in colors[:max_colors]]


def average_color(image: Any) -> str | None:
    if ImageStat is None:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        stat = ImageStat.Stat(image.convert("RGBA").convert("RGB"))
    vals = [int(round(value)) for value in stat.mean[:3]]
    return "#%02x%02x%02x" % tuple(vals)


def phash64(image: Any) -> str | None:
    if Image is None:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            gray = image.convert("RGBA").convert("L").resize((8, 8))
        flatten = getattr(gray, "get_flattened_data", None)
        values = list(flatten() if flatten else gray.getdata())
        avg = sum(values) / len(values)
        bits = 0
        for value in values:
            bits = (bits << 1) | (1 if value >= avg else 0)
        return f"{bits:016x}"
    except Exception:
        return None


def media_tags(extension: str, width: int | None, height: int | None, bytes_count: int) -> list[str]:
    tags: set[str] = set()
    if extension in {"png", "svg", "emf", "wmf"}:
        tags.add("reusable_asset_candidate")
    if extension in {"svg", "emf", "wmf"}:
        tags.add("vector_or_metafile")
    if width and height:
        area = width * height
        aspect = width / height if height else 0
        if area <= 256 * 256:
            tags.add("small_icon")
        if 2.5 <= aspect <= 12 and width >= 300:
            tags.add("banner_art")
        if width >= 600 and height <= 250:
            tags.add("wide_decorative_art")
        if area >= 600 * 350 or bytes_count >= 500_000:
            tags.add("large_background_or_photo")
    return sorted(tags)


def media_record(
    zf: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    source: SourceInfo,
    slide_refs: list[int],
) -> dict[str, Any]:
    extension = Path(info.filename).suffix.lower().lstrip(".")
    raw = zf.read(info.filename)
    record = base_record("media", source)
    record.update(
        {
            "media_id": sha256_16_bytes(f"{source.source_id}:{info.filename}".encode("utf-8")),
            "media_path": info.filename,
            "extension": extension,
            "bytes": info.file_size,
            "sha256_16": sha256_16_bytes(raw),
            "source_slide_refs": slide_refs,
            "candidate_tags": media_tags(extension, None, None, info.file_size),
        }
    )
    if Image is not None and extension in {"png", "jpg", "jpeg", "gif", "tiff", "bmp", "webp"}:
        try:
            with zf.open(info.filename) as handle:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    image = Image.open(handle)
                    image.load()
            width, height = image.size
            record.update(
                {
                    "width_px": width,
                    "height_px": height,
                    "aspect_ratio": round(width / height, 4) if height else None,
                    "mode": image.mode,
                    "average_color": average_color(image),
                    "dominant_colors": dominant_colors(image),
                    "phash64": phash64(image),
                    "candidate_tags": media_tags(extension, width, height, info.file_size),
                }
            )
        except Exception as exc:
            record["image_error"] = exc.__class__.__name__
    return record


def component_tags(cls: str, chars: int, refs: list[str]) -> list[str]:
    tags: set[str] = set()
    if cls.startswith("connector_") or cls == "shape_line":
        tags.add("editable_line")
    if cls.startswith(("shape_", "text_")) and any(
        token in cls for token in ("rect", "roundRect", "ellipse", "chevron", "arc")
    ):
        tags.add("editable_shape")
    if cls == "table":
        tags.add("editable_table")
    if cls == "group":
        tags.add("group_candidate")
    if cls == "picture" and refs:
        tags.add("picture_component")
    if chars:
        tags.add("text_component")
    return sorted(tags)


def slide_tags(stats: dict[str, int]) -> list[str]:
    tags: set[str] = set()
    if stats["picture_count"] >= 12:
        tags.add("icon_library")
    if stats["connector_count"] >= 4 or stats["editable_line_count"] >= 8:
        tags.add("consulting_line")
    if stats["group_count"] >= 8:
        tags.add("grouped_parts")
    if stats["table_count"] >= 1:
        tags.add("table")
    if stats["text_shape_count"] >= 8 and stats["shape_count"] >= 16:
        tags.add("consulting_layout")
    if stats["picture_count"] >= 1 and stats["media_ref_bytes"] >= 1_000_000:
        tags.add("decorative_art")
    if stats["connector_count"] >= 4 and stats["text_shape_count"] >= 4:
        tags.add("flow")
    if stats["shape_count"] >= 35 and stats["text_shape_count"] >= 10:
        tags.add("dense_slide")
    return sorted(tags)


def slide_scores(stats: dict[str, int]) -> dict[str, float]:
    return {
        "icon_library": round(stats["picture_count"] * 2.0 + stats["group_count"] * 0.4 + stats["shape_count"] * 0.08, 3),
        "consulting_line": round(stats["connector_count"] * 2.5 + stats["editable_line_count"] * 1.2 + stats["table_count"] * 2.0, 3),
        "editable_component": round(stats["shape_count"] * 0.7 + stats["connector_count"] * 1.2 + stats["table_count"] * 2.0 + stats["group_count"] * 0.5, 3),
        "consulting_layout": round(stats["text_shape_count"] * 1.0 + stats["shape_count"] * 0.25 + stats["connector_count"] * 0.5, 3),
        "decorative_art": round(stats["picture_count"] * 0.8 + stats["media_ref_bytes"] / 1_000_000, 3),
    }


def top_slide_candidates(slides: list[dict[str, Any]], limit: int = 20) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for key in ["icon_library", "consulting_line", "editable_component", "consulting_layout", "decorative_art"]:
        ordered = sorted(slides, key=lambda slide: slide.get("candidate_scores", {}).get(key, 0), reverse=True)
        result[key] = [slide["slide_number"] for slide in ordered[:limit]]
    return result


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def scan_deck(path: Path, out_dir: Path, privacy: str) -> dict[str, Any]:
    digest = sha256_16_file(path)
    source = SourceInfo(
        source_id=f"{safe_slug(path.stem)}-{digest}",
        name=path.name,
        path=path,
        sha256_16=digest,
        bytes=path.stat().st_size,
        privacy=privacy,
    )
    started = time.time()
    slide_records: list[dict[str, Any]] = []
    media_records: list[dict[str, Any]] = []
    component_records: list[dict[str, Any]] = []
    media_to_slides: dict[str, set[int]] = defaultdict(set)
    aggregate_shape_types: Counter[str] = Counter()

    with zipfile.ZipFile(path) as zf:
        media_infos = {info.filename: info for info in zf.infolist() if info.filename.startswith("ppt/media/")}
        slide_names = sorted(
            [name for name in zf.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", name)],
            key=natural_slide_key,
        )
        deck_slide_size = slide_size_in(zf)
        slide_area = (deck_slide_size or {}).get("width", 13.3333) * (deck_slide_size or {}).get("height", 7.5)

        for slide_number, slide_name in enumerate(slide_names, 1):
            root = read_xml(zf, slide_name)
            if root is None:
                continue
            rels = rel_targets(zf, slide_name)
            shape_types: Counter[str] = Counter()
            boxes = []
            media_refs: list[str] = []
            stats = {
                "shape_count": 0,
                "text_shape_count": 0,
                "text_char_count": 0,
                "picture_count": 0,
                "group_count": 0,
                "connector_count": 0,
                "table_count": 0,
                "editable_line_count": 0,
                "media_ref_bytes": 0,
            }
            for order, el in enumerate(root.findall(".//p:spTree/*", NS)):
                cls = shape_class(el)
                chars = text_length(el)
                refs = shape_media_refs(el, rels)
                box = bbox_in(el)
                tags = component_tags(cls, chars, refs)
                stats["shape_count"] += 1
                stats["text_char_count"] += chars
                stats["text_shape_count"] += 1 if chars else 0
                stats["picture_count"] += 1 if cls == "picture" else 0
                stats["group_count"] += 1 if cls == "group" else 0
                stats["connector_count"] += 1 if cls.startswith("connector_") else 0
                stats["table_count"] += 1 if cls == "table" else 0
                stats["editable_line_count"] += 1 if "editable_line" in tags else 0
                shape_types[cls] += 1
                aggregate_shape_types[cls] += 1
                if box:
                    boxes.append(box)
                for ref in refs:
                    media_refs.append(ref)
                    media_to_slides[ref].add(slide_number)
                if tags:
                    component = base_record("component", source)
                    component.update(
                        {
                            "component_id": sha256_16_bytes(f"{source.source_id}:{slide_number}:{order}:{cls}".encode("utf-8")),
                            "slide_number": slide_number,
                            "order": order,
                            "shape_class": cls,
                            "name_hash": name_hash(el),
                            "bbox_in": box,
                            "text_char_count": chars,
                            "media_refs": refs,
                            "candidate_tags": tags,
                        }
                    )
                    component_records.append(component)

            stats["media_ref_bytes"] = sum(media_infos[ref].file_size for ref in media_refs if ref in media_infos)
            slide = base_record("slide", source)
            slide.update(
                {
                    "slide_number": slide_number,
                    "shape_count": stats["shape_count"],
                    "shape_types": dict(shape_types.most_common()),
                    "text_shape_count": stats["text_shape_count"],
                    "text_char_count": stats["text_char_count"],
                    "picture_count": stats["picture_count"],
                    "group_count": stats["group_count"],
                    "connector_count": stats["connector_count"],
                    "table_count": stats["table_count"],
                    "media_ref_count": len(media_refs),
                    "media_ref_bytes": stats["media_ref_bytes"],
                    "layout_density": round(stats["shape_count"] / slide_area, 4) if slide_area else 0,
                    "candidate_tags": slide_tags(stats),
                    "candidate_scores": slide_scores(stats),
                    "bbox_summary": bbox_summary(boxes),
                    "media_ref_extensions": dict(Counter(Path(ref).suffix.lower().lstrip(".") for ref in media_refs)),
                }
            )
            slide_records.append(slide)

        for media_path, info in media_infos.items():
            media_records.append(media_record(zf, info, source, sorted(media_to_slides.get(media_path, set()))))

    media_ext = Counter(record.get("extension") for record in media_records)
    slide_tag_counts = Counter(tag for record in slide_records for tag in record.get("candidate_tags", []))
    media_tag_counts = Counter(tag for record in media_records for tag in record.get("candidate_tags", []))
    deck = base_record("deck", source)
    deck.update(
        {
            "source_file": str(path.expanduser().resolve()),
            "file_bytes": source.bytes,
            "indexed_at": now_local(),
            "slide_count": len(slide_records),
            "slide_size_in": deck_slide_size,
            "media_count": len(media_records),
            "media_total_bytes": sum(record.get("bytes", 0) for record in media_records),
            "media_extensions": dict(media_ext.most_common()),
            "aggregate_shape_types": dict(aggregate_shape_types.most_common()),
            "aggregate_slide_tags": dict(slide_tag_counts.most_common()),
            "aggregate_media_tags": dict(media_tag_counts.most_common()),
            "candidate_slides": top_slide_candidates(slide_records),
            "elapsed_seconds": round(time.time() - started, 2),
            "index_note": "Metadata only. Raw media, slide images, and full slide text were not extracted.",
        }
    )

    prefix = safe_slug(source.source_id)
    write_json(out_dir / "decks" / f"{prefix}.deck.json", deck)
    write_jsonl(out_dir / "slides" / f"{prefix}.slides.jsonl", slide_records)
    write_jsonl(out_dir / "media" / f"{prefix}.media.jsonl", media_records)
    write_jsonl(out_dir / "components" / f"{prefix}.components.jsonl", component_records)
    return deck


def remove_previous_indexes(out_dir: Path) -> None:
    for dirname in ["decks", "slides", "media", "components"]:
        directory = out_dir / dirname
        if directory.exists():
            for path in directory.glob("*"):
                if path.is_file():
                    path.unlink()
    for path in [out_dir / "manifest.json", out_dir / "README.md"]:
        if path.exists():
            path.unlink()
    for path in out_dir.glob("*.index.json"):
        if path.is_file():
            path.unlink()


def build_index(raw_dir: Path, out_dir: Path, privacy: str, incremental: bool = False) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    if not incremental:
        remove_previous_indexes(out_dir)
    decks = [scan_deck(path, out_dir, privacy) for path in sorted(raw_dir.glob("*.pptx"))]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "manifest",
        "generated_at": now_local(),
        "privacy": privacy,
        "asset_policy": {
            "raw_assets": "private; never commit/upload/publish",
            "indexes": "local work product unless explicitly approved for publishing",
            "local_extracted_parts": "store under the user's project assets directory by default",
            "skill_assets": "promote only after explicit user instruction and publishability confirmation",
        },
        "raw_dir": str(raw_dir.expanduser().resolve()),
        "out_dir": str(out_dir.expanduser().resolve()),
        "deck_count": len(decks),
        "slide_count": sum(deck["slide_count"] for deck in decks),
        "media_count": sum(deck["media_count"] for deck in decks),
        "media_total_bytes": sum(deck["media_total_bytes"] for deck in decks),
        "decks": [
            {
                "source_id": deck["source_id"],
                "source_name": deck["source_name"],
                "source_sha256_16": deck["source_sha256_16"],
                "file_bytes": deck["file_bytes"],
                "slide_count": deck["slide_count"],
                "media_count": deck["media_count"],
                "media_total_bytes": deck["media_total_bytes"],
                "candidate_slides": deck["candidate_slides"],
            }
            for deck in decks
        ],
    }
    write_json(out_dir / "manifest.json", manifest)
    write_readme(out_dir, manifest, decks)
    return manifest


def write_readme(out_dir: Path, manifest: dict[str, Any], decks: list[dict[str, Any]]) -> None:
    lines = [
        "# Private Asset Index",
        "",
        "This index is generated metadata for local asset retrieval. Raw source decks and derived indexes are private by default.",
        "",
        "Policy:",
        "- `assets/raw/` is private and must not be committed, uploaded, or moved into GitHub.",
        "- Index data is local unless the user explicitly approves publishing it.",
        "- No raw media, slide images, or full slide text are extracted by this indexer.",
        "",
        f"Generated: `{manifest['generated_at']}`",
        f"Schema: `{SCHEMA_VERSION}`",
        f"Decks: `{manifest['deck_count']}`",
        f"Slides: `{manifest['slide_count']}`",
        f"Media items: `{manifest['media_count']}`",
        "",
        "Deck Summary:",
    ]
    for deck in decks:
        lines.extend(
            [
                f"- `{deck['source_name']}`",
                f"  - Source id: `{deck['source_id']}`",
                f"  - Size: `{round(deck['file_bytes'] / 1024 / 1024, 1)} MB`",
                f"  - Slides: `{deck['slide_count']}`",
                f"  - Media: `{deck['media_count']}` (`{round(deck['media_total_bytes'] / 1024 / 1024, 1)} MB`)",
                f"  - Media extensions: `{deck['media_extensions']}`",
                f"  - Slide tags: `{deck['aggregate_slide_tags']}`",
                f"  - Media tags: `{deck['aggregate_media_tags']}`",
                f"  - Top consulting-line slides: `{deck['candidate_slides'].get('consulting_line', [])[:10]}`",
                f"  - Top icon-library slides: `{deck['candidate_slides'].get('icon_library', [])[:10]}`",
            ]
        )
    (out_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def iter_kind_records(index_dir: Path, kind: str) -> list[dict[str, Any]]:
    subdir = {"deck": "decks", "slide": "slides", "media": "media", "component": "components"}[kind]
    directory = index_dir / subdir
    if not directory.exists():
        return []
    records: list[dict[str, Any]] = []
    if kind == "deck":
        for path in sorted(directory.glob("*.json")):
            records.append(json.loads(path.read_text(encoding="utf-8")))
    else:
        for path in sorted(directory.glob("*.jsonl")):
            records.extend(read_jsonl(path))
    return records


def matches_query(record: dict[str, Any], tag: str | None, source: str | None, query: str | None) -> bool:
    if tag and tag not in record.get("candidate_tags", []):
        return False
    if source and source not in record.get("source_name", "") and source not in record.get("source_id", ""):
        return False
    if query and query.lower() not in json.dumps(record, ensure_ascii=False).lower():
        return False
    return True


def record_score(record: dict[str, Any], tag: str | None, score_key: str | None) -> float:
    if score_key:
        return float(record.get("candidate_scores", {}).get(score_key, 0.0))
    if tag:
        if tag in record.get("candidate_scores", {}):
            return float(record["candidate_scores"][tag])
        return 1.0 if tag in record.get("candidate_tags", []) else 0.0
    scores = record.get("candidate_scores", {})
    if scores:
        return max(float(value) for value in scores.values())
    return float(record.get("shape_count", record.get("bytes", 0)))


def compact_record(record: dict[str, Any]) -> dict[str, Any]:
    keep = [
        "record_type",
        "source_id",
        "source_name",
        "slide_number",
        "media_id",
        "component_id",
        "shape_class",
        "media_path",
        "extension",
        "bytes",
        "width_px",
        "height_px",
        "aspect_ratio",
        "shape_count",
        "shape_types",
        "text_shape_count",
        "picture_count",
        "group_count",
        "connector_count",
        "table_count",
        "media_ref_count",
        "media_ref_bytes",
        "layout_density",
        "candidate_tags",
        "candidate_scores",
        "bbox_in",
        "bbox_summary",
        "source_slide_refs",
    ]
    return {key: record[key] for key in keep if key in record}


def search_index(
    index_dir: Path,
    kind: str,
    tag: str | None,
    source: str | None,
    query: str | None,
    score_key: str | None,
    limit: int,
    full: bool,
) -> dict[str, Any]:
    records = [
        record
        for record in iter_kind_records(index_dir, kind)
        if matches_query(record, tag=tag, source=source, query=query)
    ]
    records.sort(key=lambda record: record_score(record, tag=tag, score_key=score_key), reverse=True)
    selected = records[:limit]
    return {
        "index_dir": str(index_dir),
        "kind": kind,
        "count": len(records),
        "returned": len(selected),
        "results": selected if full else [compact_record(record) for record in selected],
    }


def summarize_index(index_dir: Path) -> dict[str, Any]:
    manifest_path = index_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    tag_counts: dict[str, Counter[str]] = {"slide": Counter(), "media": Counter(), "component": Counter()}
    for kind in tag_counts:
        for record in iter_kind_records(index_dir, kind):
            tag_counts[kind].update(record.get("candidate_tags", []))
    return {
        "manifest": manifest,
        "slide_tags": dict(tag_counts["slide"].most_common()),
        "media_tags": dict(tag_counts["media"].most_common()),
        "component_tags": dict(tag_counts["component"].most_common()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and query private PPT asset indexes for png2ppt.")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Build a metadata-only index for PPTX assets.")
    build.add_argument("raw_dir", type=Path, help="Directory containing private .pptx asset decks.")
    build.add_argument("--out", required=True, type=Path, help="Output index directory.")
    build.add_argument("--privacy", default="private_local")
    build.add_argument("--incremental", action="store_true", help="Do not delete existing index files first.")

    search = sub.add_parser("search", help="Search slides, media, components, or decks.")
    search.add_argument("index_dir", type=Path)
    search.add_argument("--kind", choices=["deck", "slide", "media", "component"], default="slide")
    search.add_argument("--tag")
    search.add_argument("--source")
    search.add_argument("--query")
    search.add_argument("--score-key")
    search.add_argument("--limit", type=int, default=20)
    search.add_argument("--full", action="store_true")

    summary = sub.add_parser("summary", help="Summarize an index.")
    summary.add_argument("index_dir", type=Path)

    args = parser.parse_args()
    if args.command == "build":
        print_json(build_index(args.raw_dir, args.out, privacy=args.privacy, incremental=args.incremental))
    elif args.command == "search":
        print_json(
            search_index(
                args.index_dir,
                kind=args.kind,
                tag=args.tag,
                source=args.source,
                query=args.query,
                score_key=args.score_key,
                limit=args.limit,
                full=args.full,
            )
        )
    elif args.command == "summary":
        print_json(summarize_index(args.index_dir))


if __name__ == "__main__":
    main()
