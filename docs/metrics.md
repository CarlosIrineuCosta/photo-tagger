# Photo Tagger Metrics

The Photo Tagger includes evaluation metrics to assess tagging performance on labeled datasets.

## Metrics Overview

### Precision@K
Precision@K measures the proportion of correct tags among the top-k predicted tags for each image. This metric is useful when you're primarily interested in the quality of the highest-confidence predictions.

- **Range**: 0.0 to 1.0 (higher is better)
- **Use case**: Evaluating the top-ranked predictions that users are most likely to see

### Stack Coverage
Stack coverage measures the proportion of expected tags that appear anywhere in the predicted tags list, regardless of position. This metric evaluates overall tag recall.

- **Range**: 0.0 to 1.0 (higher is better)
- **Use case**: Assessing whether the system can find all relevant tags, even if ranked lower

## Data Preparation

Create a JSONL file (one JSON object per line) with the following fields:

```json
{"image_id": "example001.jpg", "predicted_tags": ["beach", "sunset", "ocean"], "expected_tags": ["beach", "sunset"]}
{"image_id": "example002.jpg", "predicted_tags": ["forest", "trees", "nature"], "expected_tags": ["forest", "hiking"]}
```

- `image_id`: Unique identifier for the image
- `predicted_tags`: List of tags predicted by the Photo Tagger (ordered by confidence)
- `expected_tags`: List of ground truth tags for evaluation

## CLI Usage

Compute metrics using the `metrics` subcommand:

```bash
python -m app.cli.tagger metrics --dataset /path/to/eval_dataset.jsonl --k 5
```

Parameters:
- `--dataset`: Path to the JSONL evaluation dataset (required)
- `--k`: Number of top predictions to consider for Precision@K (default: 5)

The command outputs a table with both metrics values and the total number of evaluated images.
