import argparse
import json
from pathlib import Path
import numpy as np
from sklearn.metrics import silhouette_score

from app.core.medoid import compute_folder_medoids
from app.scanner import crawl

def main():
    parser = argparse.ArgumentParser(description="Medoid clustering tuning harness.")
    parser.add_argument("dataset_path", type=str, help="Path to the image dataset.")
    parser.add_argument("embeddings_path", type=str, help="Path to the .npy file with embeddings.")
    parser.add_argument("--min-cluster-size", type=int, default=3, help="Minimum cluster size.")
    parser.add_argument("--embedding-threshold", type=float, default=0.82, help="Embedding similarity threshold.")
    parser.add_argument("--max-embedding-clusters", type=int, default=5, help="Maximum number of embedding clusters.")
    parser.add_argument("--use-tag-clusters", action="store_true", help="Enable tag-based clustering.")
    parser.add_argument("--cluster-mode", type=str, default="hybrid", choices=["simple", "hybrid"], help="Clustering mode.")

    args = parser.parse_args()

    # Load data
    print("Loading embeddings...")
    embeddings = np.load(args.embeddings_path)
    
    print("Scanning dataset...")
    # We need to map file paths to indices in the embeddings array.
    # The crawl function returns a list of dicts, which we can use for this.
    image_meta = crawl(roots=[args.dataset_path], include_ext=[".jpg", ".jpeg", ".png"], exclude_regex=[])
    path_to_index = {meta["path"]: i for i, meta in enumerate(image_meta)}

    # For simplicity, we'll treat the whole dataset as one folder
    folder_to_indices = {"dataset": list(range(len(image_meta)))}

    # Run medoid computation
    print("Computing medoids...")
    medoid_results = compute_folder_medoids(
        folder_to_indices=folder_to_indices,
        embeddings=embeddings,
        use_tag_clusters=args.use_tag_clusters,
        min_cluster_size=args.min_cluster_size,
        cluster_mode=args.cluster_mode,
        embedding_cluster_threshold=args.embedding_threshold,
        max_embedding_clusters=args.max_embedding_clusters,
    )

    # Prepare data for silhouette score
    # We need a list of samples and a corresponding list of cluster labels
    folder_result = medoid_results.get("dataset")
    if not folder_result or not folder_result.get("clusters"):
        print("No clusters were formed.")
        return

    clusters = folder_result["clusters"]
    
    labels = np.full(len(image_meta), -1, dtype=int) # -1 for noise/unclustered
    cluster_count = 0
    for i, cluster in enumerate(clusters):
        for member_index in cluster["members"]:
            labels[member_index] = i
        cluster_count += 1

    # Filter out unclustered samples for silhouette score calculation
    clustered_indices = np.where(labels != -1)[0]
    if len(clustered_indices) < 2 or len(set(labels[clustered_indices])) < 2:
        print("Not enough clusters or samples to compute silhouette score.")
        score = -1
    else:
        score = silhouette_score(embeddings[clustered_indices], labels[clustered_indices])

    # Report results
    print("\n--- Medoid Tuning Results ---")
    print(f"Parameters:")
    print(f"  - Min cluster size: {args.min_cluster_size}")
    print(f"  - Embedding threshold: {args.embedding_threshold}")
    print(f"  - Max embedding clusters: {args.max_embedding_clusters}")
    print(f"  - Use tag clusters: {args.use_tag_clusters}")
    print(f"  - Cluster mode: {args.cluster_mode}")
    print("\nResults:")
    print(f"  - Number of clusters found: {cluster_count}")
    print(f"  - Number of unclustered items: {len(image_meta) - len(clustered_indices)}")
    print(f"  - Silhouette Score: {score:.4f}")
    print("---------------------------")

if __name__ == "__main__":
    main()
