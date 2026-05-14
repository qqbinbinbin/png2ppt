# Asset Index

`png2ppt` can use local asset libraries for semantic icons, line patterns, decorative art, and reusable consulting-slide parts. The public skill stores only the indexing tool and schema. User-owned source decks and indexes derived from them are private local work products by default.

## Privacy Boundary

- Never commit raw asset decks such as `assets/raw/*.pptx`.
- Treat index data generated from private decks as local unless the user explicitly approves publishing it.
- Do not extract or copy raw media by default. Build metadata first, then extract only task-needed parts.
- Do not store full slide text in the index. Store counts and short hashes only unless the user explicitly asks for text indexing.
- Promote extracted parts into the skill repository only after explicit user approval and publishability confirmation.

## Directory Layout

Recommended local layout:

```text
assets/
├── raw/                  # private source decks, never committed
├── index/                # private searchable metadata
│   ├── manifest.json
│   ├── README.md
│   ├── decks/
│   ├── slides/
│   ├── media/
│   └── components/
├── parts/                # local extracted reusable parts
└── extracted/            # extraction scratch space
```

The index is intentionally split:

- `manifest.json`: source inventory, schema version, policy, and aggregate counts.
- `decks/*.deck.json`: one file per source deck with deck-level summary and candidate slide rankings.
- `slides/*.slides.jsonl`: one JSON object per slide for fast streaming search.
- `media/*.media.jsonl`: one JSON object per media item with dimensions, extension, hash, and visual summaries.
- `components/*.components.jsonl`: one JSON object per top-level shape/group/table/picture candidate.

## Index Schema

Every record includes:

- `schema_version`
- `record_type`
- `source_id`
- `source_name`
- `source_sha256_16`
- `privacy`

Slide records include:

- `slide_number`
- `shape_count`
- `shape_types`
- `text_shape_count`
- `text_char_count`
- `picture_count`
- `group_count`
- `connector_count`
- `table_count`
- `media_ref_count`
- `media_ref_bytes`
- `layout_density`
- `candidate_tags`
- `candidate_scores`
- `bbox_summary`

Media records include:

- `media_id`
- `media_path`
- `extension`
- `bytes`
- `sha256_16`
- `width_px`
- `height_px`
- `aspect_ratio`
- `mode`
- `average_color`
- `dominant_colors`
- `phash64`
- `source_slide_refs`
- `candidate_tags`

Component records include:

- `component_id`
- `slide_number`
- `shape_class`
- `name_hash`
- `bbox_in`
- `text_char_count`
- `media_refs`
- `candidate_tags`

## Search Strategy

For consulting PPT reconstruction:

1. Search `slides` for `consulting_line`, `flow`, `grid`, or `icon_library`.
2. Search `media` for aspect ratio, dominant color, and tags such as `small_icon`, `banner_art`, `skyline_art`, or `decorative_texture`.
3. Search `components` for editable line groups, connectors, rounded rectangles, tables, and reusable node shapes.
4. Extract only the chosen part from the raw deck into local `assets/parts/`.
5. Record extraction provenance locally so a later reconstruction can reuse the same part.

## Commands

Build a private local index:

```bash
python3 scripts/asset_index.py build assets/raw --out assets/index
```

Search indexed slides/media/components:

```bash
python3 scripts/asset_index.py search assets/index --kind slide --tag consulting_line --limit 20
python3 scripts/asset_index.py search assets/index --kind media --tag small_icon --limit 20
python3 scripts/asset_index.py search assets/index --kind component --tag editable_line --limit 20
```

Summarize the index:

```bash
python3 scripts/asset_index.py summary assets/index
```
