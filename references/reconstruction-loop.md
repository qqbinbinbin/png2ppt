# High-Fidelity Screenshot To Editable PPT Loop

Use this loop when the user wants a bitmap-backed slide rebuilt as editable PowerPoint and cares about line/layout fidelity.

## 1. Lock The Validation Scope

Do not compare full-deck previews if the screenshot is only one embedded image region. Extract the exact reference bitmap from the PPTX package or use the user-provided image at its native size.

For a PPTX bitmap-backed slide:

```python
from zipfile import ZipFile
from pathlib import Path

with ZipFile("input.pptx") as z:
    Path("reference.png").write_bytes(z.read("ppt/media/image1.png"))
```

Use the same reference size for every candidate render. If the candidate is rendered from a PPTX, crop to the replaced picture bounds or generate a temporary deck whose canvas matches the reference image.

Before any extraction, rendering, or audit, initialize a job directory. Keep the final PPTX next to the source PNG and put every non-final generated file under the job directory:

```text
<source-dir>/<job-name>.pptx      # final PPTX
<source-dir>/png2ppt/<job-name>/work/
                                  # previews, summaries, rounds, audits, renders, specs, logs, tmp
```

Do not write round files, audit reports, masks, specs, or temporary renders next to the source PNG.

## 2. Reconstruct Structure Before Icons

Prioritize, in this order:

1. Canvas, margins, title blocks, page chrome.
2. Large panels/cards and their border radius.
3. Separators, dotted lines, vertical dividers, orbit/circle guides.
4. Text boxes and font sizes.
5. Icon semantic replacements.
6. Shadows and subtle gradients.

Icons may be PNG and semantically close. Lines, card positions, table rows, divider locations, and spacing must be geometrically close.

If the user explicitly deprioritizes icon editability, do not spend iteration budget hand-drawing icons. Use PNG icon-library replacements and spend the loop on editable text, panels, separators, tables, flow nodes, and guide geometry.

## 2.1. Profile Before Choosing A Strategy

Run the source image through `scripts/style_profile.py` before choosing a reconstruction strategy. The profile captures:

- Canvas size and aspect ratio.
- Background color/lightness and foreground bounding box.
- Dominant foreground colors and rough color-family ratios.
- Edge density, line density, dark-text ratio, and content/text block counts.
- Horizontal/vertical line candidates and large content blocks.
- A recommendation: PNG placement, simple native rebuild, hybrid rebuild, native/hybrid rebuild, or texture-backed hybrid rebuild.

Use this profile to adapt to the current image. Do not infer that a new image uses the same grid, palette, font scale, or component system as earlier samples.

After profiling, query `scripts/style_memory.py nearest` if a memory file exists. Similar previous jobs can suggest what worked, but they are not templates. Copy only reusable strategy decisions, such as "keep icons as PNG" or "tune divider positions before typography"; derive geometry from the current PNG.

If the profile reports a dark background, high palette entropy, many fine edges, and neutral/orange foreground families, do not rebuild as flat shapes only. Use a texture-backed hybrid:

- Add a cropped or synthesized low-opacity PNG background/texture layer for noise, glow, gradients, and material feel.
- Rebuild text, cards, separators, arrows, and main geometry as editable PPT objects above it.
- Keep the texture layer visibly controlled at the back; do not use it as a hidden full-slide screenshot substitute when editability is required.
- Audit both full-pixel fidelity and a non-text/non-texture structure mask so noise does not dominate decisions.

## 3. Use A Template Model

Build a page-specific layout model before drawing:

```python
regions = {
    "header": (40, 32, 1430, 125),
    "left_panel": (40, 184, 1040, 540),
    "right_panel": (1102, 184, 528, 540),
    "bottom_strip": (40, 750, 1590, 145),
}
```

Then draw from this model with reusable primitives:

- `panel(x, y, w, h, radius, border, shadow)`
- `section_header(icon, label, x, y)`
- `list_row(icon, text, x, y, separator_width)`
- `pill(x, y, w, h, radius)`
- `dotted_orbit(cx, cy, rx, ry, segments)`

Avoid hand-placing every text line independently once the pattern is visible.

For a commercial/publishable workflow, prefer a neutral component spec over ad hoc drawing code:

- `canvas`: source width, source height, slide ratio.
- `theme`: observed background, text colors, accent colors, border colors.
- `regions`: detected or manually confirmed major panels, tables, headers, sidebars, strips, and diagrams.
- `components`: text boxes, cards, dividers, icons, connectors, tables, chart placeholders.
- `strategy`: which elements must be editable and which are allowed to remain PNG.

Project-specific scripts may translate this spec into `python-pptx`, PptxGenJS, or another renderer. The skill should keep the spec/audit loop generic.

## 4. Audit Every Iteration

Run:

```bash
python3 /path/to/png2ppt/scripts/visual_fidelity_audit.py \
  --reference reference.png \
  --candidate png2ppt/<job-name>/work/renders/round_01.png \
  --out-dir png2ppt/<job-name>/work/audits/round_01 \
  --fail-on-threshold
```

Default gates:

- `edge_iou >= 0.88`
- `line_iou >= 0.88`
- `missing_structure_ratio <= 0.04`
- `extra_structure_ratio <= 0.04`
- `pixels_over_48 <= 0.03`

For early drafts, treat these as diagnostics. For final delivery, do not claim high fidelity unless the metrics pass or the remaining failures are explicitly explained.

Use metric suites, not a single score. For editable PPT reconstruction, track at least:

- `edge_iou` / `line_iou` for global structure.
- `blue_structure_iou` for corporate blue panels, rules, pills, guides, and icon strokes.
- `dark_text_iou` for typography fit.
- `pixels_over_48` and `mean_abs_diff` for overall visual drift.
- `text_roi_iou` or OCR/text-mask fit when OCR is available.
- `non_text_structure_iou` for panels, cards, separators, arrows, and layout geometry.

Changing icon libraries can lower `edge_iou` while improving semantic usefulness. Treat that as acceptable only when the user has said icons need not be editable or exact.

If the user lowers font/style consistency priority, add a **non-text structure mask** for decision-making. Exclude title/body/list text ROIs and score only panels, borders, separators, cards, flow nodes, orbit guides, blue pills, and structural marks. Use this score to pick geometry changes, while still reporting the standard audit separately.

## 4.1. Consulting Blueprint Pages

For dense consulting PPT pages, `style_profile.py` may classify the page as `consulting_blueprint`. This style is typically a white 16:9 canvas with deep-blue title hierarchy, a dark left chapter badge, pale-blue cards/tables, many thin separators, numbered process steps, arrow connectors, and a footer conclusion/output strip.

Use this reconstruction order:

1. Detect global frame: left badge, title block, top-right page counter/skyline, body region, bottom strip.
2. Extract the shared theme: deep navy, accent blue, light-blue fills, blue-gray borders, row fills, arrow fills, and footer blue.
3. Convert line detections into grid primitives: rows, columns, card boundaries, section dividers, and connector rails.
4. Rebuild cards/tables/steps as editable PPT shapes first, then text, then PNG icons/decorative art.
5. Keep skyline/building art and icons as PNG unless the user explicitly asks to edit them.
6. Audit line/table geometry separately from text style; for this style, structural fidelity matters more than exact icon artwork.

For batches, do not hand-code every page. Create a small style benchmark set first, then reuse:

- theme tokens,
- badge/title/footer primitives,
- card/table/step primitives,
- icon PNG strategy,
- regression thresholds for non-text structure.

## 5. Read The Audit Images

`edge_overlay_ref_blue_candidate_red.png`:

- Blue only: reference structure missing in candidate. Add/move lines, borders, text blocks.
- Red only: extra candidate structure. Remove oversized borders, wrong dividers, extra text strokes.
- Green: aligned structure.

`pixel_diff_heatmap.png`:

- Red around text means font weight/size/line spacing mismatch.
- Red around card edges means radius, shadow, or border mismatch.
- Red in large filled regions means color/gradient mismatch.

`structure_boxes_ref_blue_candidate_red.png`:

- Misaligned boxes reveal region-level layout drift faster than pixel heatmaps.

## 5.1. Diagnose Typical Failures

If large panels are mostly green but text is red/blue:

- Fix font family, font weight, font size, and line height before moving boxes.
- Prefer the reference's apparent typography over the original PPT theme.
- CJK text often needs Microsoft YaHei / PingFang SC / Source Han Sans checks by platform.
- Run small font-size/font-family variants as separate candidates. Pick the version with the best combined `edge_iou`, `dark_text_iou`, and pixel metrics; do not keep a size rollback unless it beats the previous best.

If card borders are green but rounded corners show red/blue:

- Tune radius and line width. PowerPoint rounded rectangle adjustment values are not pixel radii; verify by render.
- Avoid heavy shadows until geometry is correct.

If dotted or circular guides are red/blue:

- Use many short connector segments or a rasterized guide if PPT arc rendering drifts.
- Match center, radius, segment length, and dash gaps from the reference.

If validation scope metrics are extremely poor (`edge_iou < 0.2`):

- Suspect scope mismatch first. Compare whether the candidate includes extra title/footer or has been cropped differently.
- Do not tune the slide until reference and candidate canvas sizes and content scope match.

## 6. Integrate Template Beautification

When the user asks for template beautification rather than strict reconstruction, use presentation design skills such as `elite-powerpoint-designer` after the structure pass. Do not apply beautification before matching the reference geometry; it can make the deck prettier while reducing fidelity.

For strict high-fidelity reproduction:

- Do not introduce a new palette.
- Do not simplify the layout.
- Do not replace thin separators with decorative cards.
- Do not change title hierarchy.

For "improve while preserving template":

- Keep region boundaries and grid.
- Improve icon consistency.
- Normalize font sizes within equivalent row types.
- Harmonize border/shadow tokens.

## 7. Delivery Checklist

- Reference scope is correct and documented.
- Style profile is saved under `work/specs/style_profile.json`.
- Similar memory records, if used, are treated as hints and not copied blindly.
- Candidate render uses the same pixel size.
- Visual audit metrics are attached.
- Large old bitmap layer is removed from PPTX.
- Text and shapes are editable where the user expects editability.
- Icons can remain PNG unless the user explicitly requests editable icons.
- The final PPTX is next to the source PNG.
- `png2ppt/<job-name>/work/` contains final preview images, summaries/reports, intermediate rounds, audits, renders, specs, logs, and temporary files.
- Run records and style memory are updated with the final decision, metrics, and next improvement.

## External Tooling Notes

Current external options worth knowing:

- SlideForge offers screenshot/photo/reference-image to editable PPTX using a vision LLM that identifies text, shapes, charts, and positions, then renders native PPTX. This confirms the right architecture for high fidelity: image understanding -> structured component spec -> native PPT renderer.
- PPTAgent-style research uses an edit-based workflow with evaluation/reflection rather than one-shot generation. This supports a local loop of render -> visual audit -> edit.
- PptxGenJS and python-pptx can insert PNG assets reliably. For exact visual restore, keep icons and complex graphics as PNG unless the user explicitly needs editable reconstruction.

Local skill implementation should therefore mimic the robust parts:

1. Build an intermediate region/component spec before drawing.
2. Render native PPT shapes from the spec.
3. Compare rendered output against the reference image.
4. Iterate on geometry tokens and typography before changing icons.
5. Normalize renderer output to the exact validation scope. macOS Quick Look can render a 16:9 PPT thumbnail a few pixels taller than the reference; crop or resize to the reference before audit.
