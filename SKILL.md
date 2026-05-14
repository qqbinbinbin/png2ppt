---
name: png2ppt
description: Reconstruct PNG screenshots or slide images as editable PowerPoint content. Use when working with PNG-to-PPTX reconstruction, editable text/shapes, high-fidelity line/layout restoration, component-spec generation, and visual-diff-driven native PPT reconstruction.
---

# png2ppt

## Decision Rule

This skill has one delivery mode: **editable native PPT reconstruction**.

Do not create a PPTX by inserting the source PNG as a full-slide picture. A full-slide screenshot layer is only allowed as a temporary reference during local analysis and must not remain in the final deliverable.

Rebuild text, lines, panels, cards, tables, flow nodes, and other layout geometry as editable PPT objects. Icons and decorative artwork may be simplified into editable symbols or replaced by small semantic assets only when they are not the page's editable substance; never use the original full-page PNG as the delivered content.

## Fidelity Answer

Editable native PPT reconstruction improves editability but can reduce pixel-perfect parity because PowerPoint renders fonts, shadows, antialiasing, and icon details differently from the source image.

Practical ranking:

1. **Required final mode:** native PPT shapes/text for the slide structure and text.
2. **Allowed shortcut:** small semantic icon/art assets only when icon editability is not required.
3. **Forbidden final mode:** source PNG placed as the slide content.

## Workflow

1. Inspect the source: identify editable text, structural geometry, icons, decorative art, and complex bitmap regions.
2. Initialize the output layout before creating artifacts: the final PPTX goes next to the source PNG; all rounds, audits, specs, logs, previews, and temporary renders go under `png2ppt/<job-name>/work/`.
3. Create a style profile before reconstruction. Use `scripts/style_profile.py` to extract background, palette, edge density, line density, content blocks, text blocks, and a first-pass strategy recommendation.
4. Query style memory when available. Use similar previous profiles as hints, not as a template override.
5. Lock the validation scope. If the source image is embedded in PPTX, extract that exact bitmap instead of comparing full-slide previews.
6. For slide reconstruction: keep headings, text, panels, lines, tables, and flow nodes as editable PPT objects; simplify or semantically replace icons when needed.
7. Reconstruct structure before icons: canvas, panels, borders, separators, dotted lines, dividers, then text and icons.
8. When icons do not need editing, use PNG icon-library semantic replacements and spend iteration budget on editable structure and typography.
9. Remove any source screenshot/bitmap layer and prune stale media/relationships from the PPTX package.
10. Run visual fidelity audit and iterate until structure metrics pass or remaining failures are explicitly explained.
11. Record the run in both the job report and style memory so future runs can retrieve strategy/metric lessons from similar images.

## Adaptive Loop

Do not hardcode a project-specific template into this skill. Template-specific rebuilders, specs, and one-off coordinate maps belong in the project work directory, not in the published skill.

For editable or hybrid reconstruction, use this loop:

1. **Profile:** run `style_profile.py` and save `work/specs/style_profile.json`.
2. **Retrieve:** run `style_memory.py nearest` to find similar previous profiles when memory exists.
3. **Plan:** choose `simple_native_reconstruction`, `hybrid_reconstruction`, `native_or_hybrid_reconstruction`, `consulting_blueprint_hybrid_reconstruction`, or `texture_backed_hybrid_reconstruction` from the profile plus user requirements.
4. **Spec:** create a region/component spec from the image's detected layout. Keep it data-driven where possible.
5. **Render:** generate a PPTX candidate and a normalized PNG render.
6. **Audit:** run visual fidelity and PPTX package checks.
7. **Improve:** change geometry, text fit, line widths, and structural tokens before changing icons.
8. **Remember:** append decision, metrics, and the next improvement to style memory.

The memory is guidance, not truth. If a new PNG has a different palette, density, aspect ratio, or information architecture, profile it and derive a new spec instead of copying an old layout.

## Consulting Blueprint Style

When `style_profile.py` reports `style_family.name = consulting_blueprint` or `primary = consulting_blueprint_hybrid_reconstruction`, treat the page as a dense consulting PPT template:

- Preserve the fixed 16:9 grid, margins, title area, side badge, page counter, skyline/decorative art, cards, arrows, numbered steps, and footer conclusion/output strip.
- Rebuild title, subtitles, section labels, cards, tables, dividers, arrows, and numbered flow nodes as editable PPT text/shapes.
- Use PNG assets for icons, decorative skyline/building artwork, glow textures, and other non-critical illustrations.
- Extract a reusable theme from the sample set: deep navy title/strokes, blue accents, light-blue fills, white canvas, thin blue-gray borders, and compact CJK typography.
- Build from a component spec (`theme`, `regions`, `components`, `connectors`, `footer`) before drawing individual objects.
- Spend iteration budget on line/table geometry, row heights, column boundaries, arrow positions, and footer strips before icon exactness.
- For 100+ page batches, process 3-5 representative pages first, save profiles/audits/regression reports, then reuse the detected theme and component primitives for the rest.

## Quality Methods To Borrow

Useful skill patterns from the open skills ecosystem:

- **PPTX QA discipline:** render slides to images and check for placeholder text, overlap, text overflow, low contrast, stale large media, and package hygiene.
- **Design-system extraction:** convert each PNG into tokens before drawing: colors, fonts, spacing, radius, shadow, stroke, density, and component rhythm.
- **Theme factory:** classify the visual style before rendering. Generate/apply a coherent theme such as blue corporate, dark technical, warm editorial, or minimal grayscale.
- **OCR-first reconstruction:** use OCR/text ROI extraction for text boxes and line wrapping instead of relying on manual transcription or guessed positions.
- **Texture-backed hybrid:** for dark, photographic, noisy, glassy, or gradient-heavy slides, keep layout/text/cards editable but add a controlled PNG texture/background layer so pixel and structure metrics are not destroyed by flat native shapes.
- **Final polish pass:** after metrics improve, run a focused pass on spacing, type fit, line weights, contrast, and clipping before delivery.

## Output Layout

Keep the final PPTX next to the source PNG. Put every non-final artifact under one job directory:

```text
<source-dir>/
├── <job-name>.png
├── <job-name>.pptx
└── png2ppt/<job-name>/work/
    ├── rounds/
    ├── audits/
    ├── renders/
    ├── specs/
    ├── reports/
    ├── logs/
    └── tmp/
```

Only the final PPTX belongs next to the source PNG. Everything else belongs in `png2ppt/<job-name>/work/`, including final preview images, summaries/reports, round PPTX files, Quick Look/LibreOffice renders, audit images, metrics JSON, component specs, masks, scratch scripts, and logs.

## Script

Use `scripts/init_job.py` to create and print the standard paths:

```bash
python3 /path/to/png2ppt/scripts/init_job.py image1.png --root ./png2ppt
```

Use `scripts/visual_fidelity_audit.py` to compare a reference image and candidate render:

```bash
python3 /path/to/png2ppt/scripts/visual_fidelity_audit.py \
  --reference reference.png \
  --candidate png2ppt/image1/work/renders/round_01.png \
  --out-dir png2ppt/image1/work/audits/round_01 \
  --fail-on-threshold
```

Default high-fidelity gates: `edge_iou >= 0.88`, `line_iou >= 0.88`, `missing_structure_ratio <= 0.04`, `extra_structure_ratio <= 0.04`, and `pixels_over_48 <= 0.03`.

Use `scripts/regression_compare.py` after a rerun to prove the skill did not materially regress versus a saved baseline:

```bash
python3 /path/to/png2ppt/scripts/regression_compare.py \
  --baseline png2ppt/image1/work/audits/final/metrics.json \
  --candidate png2ppt/image1/work/regression/audit/metrics.json \
  --quality png2ppt/image1/work/regression/quality.json \
  --out png2ppt/image1/work/regression/regression_report.json \
  --fail-on-regression
```

Use `scripts/style_profile.py` before editable reconstruction:

```bash
python3 /path/to/png2ppt/scripts/style_profile.py \
  image1.png \
  --out png2ppt/image1/work/specs/style_profile.json \
  --debug-dir png2ppt/image1/work/tmp/style_profile
```

Use `scripts/style_memory.py` to retrieve and append adaptive lessons:

```bash
python3 /path/to/png2ppt/scripts/style_memory.py nearest \
  --profile png2ppt/image1/work/specs/style_profile.json \
  --limit 5

python3 /path/to/png2ppt/scripts/style_memory.py append \
  --profile png2ppt/image1/work/specs/style_profile.json \
  --quality-json png2ppt/image1/work/reports/quality.json \
  --audit-json png2ppt/image1/work/audits/final/metrics.json \
  --final-pptx image1.pptx \
  --decision "hybrid reconstruction: editable layout, PNG icons" \
  --improvement "next run should tune line positions before icon substitutions"
```

## PPTX Checks

For modified decks, verify:

```bash
python3 - <<'PY'
from pptx import Presentation
prs = Presentation("output.pptx")
for i, s in enumerate(prs.slides, 1):
    pictures = sum(1 for sh in s.shapes if sh.shape_type == 13)
    text = sum(1 for sh in s.shapes if getattr(sh, "has_text_frame", False) and sh.text_frame.text.strip())
    print(i, len(s.shapes), pictures, text)
PY
```

Check for old screenshots:

```bash
python3 - <<'PY'
from zipfile import ZipFile
with ZipFile("output.pptx") as z:
    print([n for n in z.namelist() if n.startswith("ppt/media/") and z.getinfo(n).file_size > 500000])
PY
```

## Notes

- If the user says “不需要编辑图标/快速实现”, simplify icons or use small semantic replacements; do not insert the source slide PNG.
- If the user says “高保真”, improve native structure, typography, and line geometry; do not use full-slide PNG placement as the final deliverable.
- If the user says “可编辑”, rebuild key content as text/shapes and keep complex art/icons simplified unless editability is required.
- If the user dislikes fidelity, run the visual audit and fix structural drift/typography before changing icon strategy.
- Normalize rendered PPT previews to the reference bitmap dimensions before audit; some renderers add 1-2 pixels to thumbnail height.
- If the user asks for PPT beautification, use the installed `elite-powerpoint-designer` skill after structural fidelity is acceptable; beautification must not break the reference grid unless the user allows redesign.
- For rail/overflow/layout verification ideas, adapt the installed `pptx-html-fidelity-audit` skill's geometry-first discipline even when the source is an image rather than HTML.

For iterative high-fidelity reconstruction, read `references/reconstruction-loop.md`.
