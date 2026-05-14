#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def slugify(value: str) -> str:
    stem = Path(value).stem
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-._")
    return slug or "png2ppt-job"


def init_job(source: Path, root: Path, name: str | None = None) -> dict[str, str]:
    source = source.expanduser().resolve()
    job_name = name or slugify(source.name)
    root = root.expanduser()
    job_dir = (source.parent / root if not root.is_absolute() else root) / job_name
    paths = {
        "source": str(source),
        "job_dir": str(job_dir),
        "work": str(job_dir / "work"),
        "rounds": str(job_dir / "work" / "rounds"),
        "audits": str(job_dir / "work" / "audits"),
        "renders": str(job_dir / "work" / "renders"),
        "specs": str(job_dir / "work" / "specs"),
        "reports": str(job_dir / "work" / "reports"),
        "logs": str(job_dir / "work" / "logs"),
        "tmp": str(job_dir / "work" / "tmp"),
        "final_pptx": str(source.parent / f"{job_name}.pptx"),
        "final_preview": str(job_dir / "work" / "renders" / "final.png"),
        "summary": str(job_dir / "work" / "reports" / "summary.md"),
    }
    for key in ("rounds", "audits", "renders", "specs", "reports", "logs", "tmp"):
        Path(paths[key]).mkdir(parents=True, exist_ok=True)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize a png2ppt job output layout.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--root", type=Path, default=Path("png2ppt"))
    parser.add_argument("--name")
    parser.add_argument("--shell", action="store_true", help="Print shell exports instead of JSON.")
    args = parser.parse_args()

    paths = init_job(args.source, args.root, args.name)
    if args.shell:
        for key, value in paths.items():
            env_key = "PNG2PPT_" + key.upper()
            print(f'export {env_key}="{value}"')
    else:
        print(json.dumps(paths, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
