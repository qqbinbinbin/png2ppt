# png2ppt

Codex skill for reconstructing PNG screenshots or slide images as editable PowerPoint content.

The skill has one delivery mode:

- **Editable native PPT reconstruction:** rebuild text, layout lines, panels, cards, tables, and flow geometry as native PPT objects. Icons and decorative art may be simplified or semantically replaced, but the source PNG must not be delivered as a full-slide picture.

It is designed for iterative, visual-diff-driven work instead of one-shot guessing: profile the source image, build a candidate PPTX, render it, audit the render against the source PNG, then compare metrics against a saved baseline.

## Install

Install from the public GitHub repository. This direct-install command works even before `skills.sh` search indexes the repository:

```bash
npx skills add qqbinbinbin/png2ppt --skill png2ppt -y
```

Install globally:

```bash
npx skills add qqbinbinbin/png2ppt --skill png2ppt -g -y
```

List the skill without installing:

```bash
npx skills add qqbinbinbin/png2ppt --list
```

## When To Use

Use this skill when you need to:

- Turn PNG screenshots or slide images into editable `.pptx`.
- Reconstruct key slide content as editable PowerPoint objects.
- Preserve layout, lines, cards, panels, tables, and flow diagrams.
- Rebuild dense consulting-style PPT pages with blue corporate grids, badges, cards, process steps, arrows, and footer strips.
- Use simple semantic icon replacements when icon editability is not important.
- Audit visual fidelity and prove that an iteration did not regress.

The final PPTX must not be a source-image-backed deck. A screenshot layer can be used only as a temporary local reference and must be removed before delivery.

## Output Layout

Final deliverables stay next to the source image:

```text
source-dir/
├── image1.png
├── image1.pptx
└── png2ppt/image1/work/
    ├── audits/
    ├── logs/
    ├── renders/
    ├── reports/
    ├── rounds/
    ├── specs/
    └── tmp/
```

Only the final `.pptx` belongs beside the source PNG. All previews, reports, intermediate rounds, audit images, metrics, component specs, and scratch files belong under `png2ppt/<job>/work/`.

## Core Scripts

Create standard job paths:

```bash
python3 scripts/init_job.py image1.png --root ./png2ppt
```

Profile an image before reconstruction:

```bash
python3 scripts/style_profile.py \
  image1.png \
  --out png2ppt/image1/work/specs/style_profile.json
```

Audit a rendered candidate against the source image:

```bash
python3 scripts/visual_fidelity_audit.py \
  --reference image1.png \
  --candidate png2ppt/image1/work/renders/round_01.png \
  --out-dir png2ppt/image1/work/audits/round_01
```

Compare a rerun with a saved baseline:

```bash
python3 scripts/regression_compare.py \
  --baseline png2ppt/image1/work/audits/final/metrics.json \
  --candidate png2ppt/image1/work/regression/audit/metrics.json \
  --quality png2ppt/image1/work/regression/quality.json \
  --fail-on-regression
```

Build a private metadata index for local PPT asset libraries:

```bash
python3 scripts/asset_index.py build assets/raw --out assets/index
python3 scripts/asset_index.py search assets/index --kind slide --tag consulting_line --limit 20
python3 scripts/asset_index.py search assets/index --kind media --tag small_icon --limit 20
```

Raw asset decks and indexes derived from private user assets are local work products by default. Do not commit them or move extracted parts into the public skill unless the user explicitly approves that promotion.

## Quality Bar

The skill treats visual quality as measurable:

- Render each candidate PPTX to PNG before judging.
- Normalize render dimensions to the reference PNG.
- Check pixel difference, edge/line IoU, missing structure, extra structure, and package hygiene.
- Run regression comparison when changing scripts or reconstruction strategy.

This does not guarantee perfect pixel-level reconstruction. PowerPoint text rendering, antialiasing, shadows, gradients, and icon detail can differ from the source image. The point is to keep the result editable while making differences visible, measurable, and improvable.

## Repository Maintenance

Validate skill changes before committing:

```bash
python3 -m py_compile scripts/*.py
npx skills add . --list
```

Do not commit user deliverables, sample work directories, rendered previews, private asset indexes, raw asset decks, extracted private parts, or project-specific slide rebuilders. Keep reusable workflows in this repository and one-off reconstruction scripts in the user's project workspace.
