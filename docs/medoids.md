# Medoid Selection Strategy

The medoid command picks a representative image per folder and can expose
clusters that deserve a closer look. It now supports two clustering modes:

- **simple** (default): optionally group images by their top tags and compute a
  medoid per tag cluster.
- **hybrid**: perform the tag pass and then run an embedding-based sweep to
  gather remaining images into high-similarity clusters.

## CLI Usage

```
python -m app.cli.tagger medoids --run-id RUN123 --cluster-mode hybrid \
  --tag-aware --cluster-min-size 2 \
  --embedding-threshold 0.86 --max-embedding-clusters 4
```

Key flags:

| Flag | Description |
| --- | --- |
| `--cluster-mode {simple,hybrid}` | choose clustering strategy |
| `--tag-aware` | enable tag-derived clusters |
| `--cluster-min-size` | minimum members required for tag clusters |
| `--embedding-threshold` | cosine similarity threshold for embedding clusters |
| `--max-embedding-clusters` | limit embedding clusters per folder (`0` = unlimited) |

Each CSV row now includes `cluster_type` and `label_hint` to make it easy to
distinguish folder-level medoids, tag clusters, and embedding clusters.

```
folder,cluster_type,cluster_tag,label_hint,cluster_size,medoid_rel_path,cosine_to_centroid
atlanta-trip,folder,,,"12","20240214/IMG_1234.jpg","0.912345"
atlanta-trip,tag,skyline,skyline,"4","20240214/IMG_1229.jpg","0.945678"
atlanta-trip,embedding,,embedding_1,"3","20240214/IMG_1238.jpg","0.921004"
```

Tag clusters inherit the tag as their `label_hint`. Embedding clusters receive
auto-generated hints (`embedding_1`, `embedding_2`, …) while tracking the member
indices internally for downstream tooling.
