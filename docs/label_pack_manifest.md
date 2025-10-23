# Structured Label Pack Manifest

The tagging pipeline keeps the newline-delimited tier files in `labels/*.txt` as
the writable source of truth for CLIP prompts. We are adding
`labels/label_pack.yaml` as a manifest that records canonical identifiers,
display metadata, and migration hints for automation. The loader will read the
manifest first, then fall back to the text files to preserve backwards
compatibility.

## Goals
- Provide deterministic IDs for every canonical label.
- Capture human-friendly names, descriptions, and tier ordering without
  hard-coding them in the frontend.
- Track aliases/synonyms used for suggestion matching and review tooling.
- Store per-label overrides (thresholds, prompts, notes) alongside the existing
  `thresholds.yaml` and `prompts.yaml` data to reduce fragmentation.
- Record promotion history so orphan graduations can be audited.

## File Layout

```yaml
version: 1
updated_at: 2024-04-01T12:00:00Z

groups:
  - id: objects
    label: Objects
    description: Physical items, props, and distinct subjects.
    path: objects.txt                # text file that mirrors this group
    default_threshold: 0.23
    supports_bulk: true
    allow_user_labels: true
    display_order: 10
  - id: scenes
    label: Scenes
    description: Locations or environmental context.
    path: scenes.txt
    default_threshold: 0.24
    supports_bulk: true
    allow_user_labels: false
    display_order: 20

labels:
  sunflower-field:
    name: Sunflower Field
    group: scenes
    text_label: sunflower field      # canonical string pushed into the .txt file
    prompt_templates:
      - "a photo taken in a {}"
      - "a {} scene"
    threshold: 0.26
    aliases:
      - field of sunflowers
      - sunflower meadow
    equivalence_group: flora-bold    # optional handle shared by related labels
    disambiguation:
      - "Use for wide outdoor vistas containing many sunflowers."
    notes: "Popular synonym in recent user tags."
  macro-closeup:
    name: Macro Close-up
    group: styles
    text_label: macro closeup
    threshold: 0.20
    aliases:
      - macro shot
      - macro photography

promotions:
  - tag: neon nightscape
    promoted_at: 2024-03-21T18:05:00Z
    user: jdoe
    group: scenes
    label_id: neon-nightscape
    source: orphan-review-20240321
```

### Field Notes

- `version` enables future schema migrations.
- `groups[].path` keeps the loader aligned with the legacy text file layout.
- `labels[...].text_label` is the normalized string persisted in the text file;
  use the canonical ID (`sunflower-field`) when cross-referencing in the API.
- `aliases` feed both equivalence reduction and orphan matching heuristics.
- `equivalence_group` is optional; the existing `equivalences.yaml` will be
  merged into explicit groups keyed by their canonical IDs during migration.
- `promotions` acts as a lightweight ledger until we replace it with a dedicated
  audit log. Entries mirror the existing `runs/tag_events.log` data and include a
  `status` field (default `pending`) so the UI can highlight items that still
  need graduation review.

## Loader Expectations

1. When `label_pack.yaml` exists the loader should:
   - build the tier → labels mapping from `groups` and `labels[*].text_label`.
   - expose canonical IDs, human labels, aliases, and thresholds on the resulting
     `LabelPack` object.
   - merge/override any `prompts.yaml` and `thresholds.yaml` data with the values
     embedded in the manifest.
2. If the manifest is absent we read the current text/yaml files exactly as we do
   today.
3. Any new label added through the API writes to `labels/<group>.txt` and appends
   a `promotions` entry so downstream tooling can reconstruct the manifest entry.

## API Contract Touchpoints

- `GET /api/tags/summary` will return:
  ```json
  {
    "groups": [
      {
        "id": "objects",
        "label": "Objects",
        "description": "...",
        "path": "labels/objects.txt",
        "canonical_count": 120,
        "supports_bulk": true,
        "tags": ["camera", "lens", "..."]
      }
    ],
    "orphan_tags": [
      {
        "name": "macro shot",
        "occurrences": 8,
        "suggested_group_id": "styles",
        "suggested_label_id": "macro-closeup",
        "confidence": 0.82
      }
    ],
    "stats": {
      "pending_graduations": 5,
      "groups": 4,
      "total_labels": 300,
      "orphan_labels": 18
    }
  }
  ```
- `POST /api/tags/promote` continues to accept the simple payload, but the
  response will now include `label_id` and `group_label`.
- `POST /api/tags/promote/bulk` will accept `{ "actions": [...] }` where each
  action contains the source tag, destination group ID, optional canonical label
  ID, and flags (e.g., `create_label: true`). Responses return per-action status,
  logging context, and any manifest updates.

These contracts give the frontend everything needed for single-click promotions,
bulk queueing, and the graduation surface described in the ongoing plan.
