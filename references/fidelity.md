# PNG Fidelity In PowerPoint

## Short Answer

PNG placement has the highest visual restoration fidelity for PowerPoint delivery because it preserves the rendered pixels. Native PPT reconstruction makes content editable, but usually lowers same-look fidelity because PowerPoint renders fonts, shadows, lines, and antialiasing differently from the source image.

## Why PNG Usually Looks More Accurate

- It preserves the final rendered pixels.
- It avoids font substitution.
- It behaves predictably across PowerPoint, Keynote, QuickLook, and PDF export.

Use large enough transparent PNGs: at least 2x the displayed dimensions, often 256-512 px for icons and 2k-4k px for full-slide art.

## Why Editable Reconstruction Can Look Different

Editable reconstruction rebuilds the slide from PowerPoint text and shape primitives. This may change:

- Text metrics and fallback fonts.
- Stroke widths and caps.
- Gradient/filter/shadow appearance.
- Icon details, raster antialiasing, and small decorative assets.

## Best Practice For Editable PPT Decks

Use hybrid reconstruction:

- Editable: titles, body text, labels, tables, cards, arrows, lines, connectors, flow nodes.
- PNG: icons, illustrations, complex charts, shadows, decorative assets.
- Native PPT shapes: simple geometric diagrams where editability matters.

## Acceptance Criteria

- Visual comparison against the original at slide size.
- Text is selectable/editable where it matters.
- No hidden full-slide screenshot remains behind rebuilt content.
- No stale large media files remain in `ppt/media`.
- Deck opens and exports preview/PDF without rendering errors.
