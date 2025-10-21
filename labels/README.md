# Photo Tagger Label Packs

This directory stores curated label tiers used by the CLIP scoring pipeline.

- Each `.txt` file is **one label per line**, lowercase.
- Update `config.yaml` (or the Config page) to point `labels_file` at this folder when using the structured pack.
- The CLI and API detect when a directory is provided and automatically merge the tiers.

```
labels/
  objects.txt
  scenes.txt
  styles.txt
  candidates.txt
  thresholds.yaml
  equivalences.yaml
  prompts.yaml
```

`candidates.txt` is optional seed vocabulary for future semantic expansion. `thresholds.yaml`, `equivalences.yaml`, and `prompts.yaml` configure tier-specific scoring behaviour.
