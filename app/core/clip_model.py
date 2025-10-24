from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence, Tuple

import numpy as np
import open_clip
import torch
from PIL import Image

try:
    import rawpy
except Exception:  # pragma: no cover - rawpy optional at import time
    rawpy = None

RAW_EXTENSIONS = {
    ".dng",
    ".nef",
    ".arw",
    ".cr2",
    ".cr3",
    ".rw2",
    ".orf",
    ".raf",
    ".srw",
}


def _chunked(sequence: Sequence[str] | Iterable[str], size: int):
    batch: list[str] = []
    for item in sequence:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def _resolve_device(model: torch.nn.Module, device: str | torch.device | None) -> torch.device:
    if device is None:
        return next(model.parameters()).device
    return torch.device(device)


def load_clip(
    model_name: str = "ViT-L-14",
    pretrained: str = "openai",
    device: str | None = None,
) -> Tuple[torch.nn.Module, object, object, torch.device]:
    """
    Load a CLIP model and return ``(model, preprocess, tokenizer, device)``.
    """
    requested_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    model, preprocess, _ = open_clip.create_model_and_transforms(
        model_name,
        pretrained=pretrained,
        device=requested_device,
    )
    model.eval()
    tokenizer = open_clip.get_tokenizer(model_name)
    return model, preprocess, tokenizer, torch.device(requested_device)


def embed_images(
    paths: Iterable[str],
    model: torch.nn.Module,
    preprocess,
    batch_size: int = 64,
    device: str | torch.device | None = None,
) -> np.ndarray:
    """
    Embed ``paths`` using ``model`` and ``preprocess`` into a float32 array.
    """
    paths = list(paths)
    if not paths:
        output_dim = getattr(getattr(model, "visual", None), "output_dim", 0)
        return np.zeros((0, int(output_dim)), dtype="float32")

    device_resolved = _resolve_device(model, device)
    model = model.to(device_resolved)
    model.eval()

    embeddings: list[np.ndarray] = []
    autocast_enabled = device_resolved.type == "cuda"

    with torch.no_grad():
        for batch_paths in _chunked(paths, max(1, batch_size)):
            images = []
            for path in batch_paths:
                image_path = Path(path)
                ext = image_path.suffix.lower()
                if ext in RAW_EXTENSIONS:
                    if rawpy is None:
                        raise RuntimeError(
                            f"rawpy is required to process RAW files (missing dependency for {image_path})"
                        )
                    with rawpy.imread(str(image_path)) as raw:
                        rgb = raw.postprocess(
                            use_auto_wb=True,
                            no_auto_bright=True,
                            output_color=rawpy.ColorSpace.sRGB,
                            output_bps=8,
                        )
                        pil_image = Image.fromarray(rgb)
                else:
                    pil_image = Image.open(image_path)
                with pil_image:
                    images.append(preprocess(pil_image.convert("RGB")))
            image_tensor = torch.stack(images).to(device_resolved)
            with torch.cuda.amp.autocast(enabled=autocast_enabled):
                feats = model.encode_image(image_tensor)
            embeddings.append(feats.detach().cpu().float().numpy())

    return np.concatenate(embeddings, axis=0)


def embed_labels(
    labels: Sequence[str],
    model: torch.nn.Module,
    tokenizer,
    device: str | torch.device | None = None,
    prompt: str = "a photo of {}",
    prompts_per_label: dict[str, Sequence[str]] | None = None,
) -> np.ndarray:
    """
    Embed text ``labels`` with the supplied CLIP ``model`` and ``tokenizer``.

    When ``prompts_per_label`` is provided, each label may expand to multiple
    prompt variants and the resulting embeddings are averaged per label.
    """
    labels = [label.strip() for label in labels if label and label.strip()]
    if not labels:
        output_dim = getattr(model, "text_projection", None)
        dim = int(getattr(output_dim, "shape", [0, 0])[1]) if output_dim is not None else 0
        return np.zeros((0, dim), dtype="float32")

    device_resolved = _resolve_device(model, device)
    model = model.to(device_resolved)
    model.eval()

    if prompts_per_label:
        prompt_variants: list[str] = []
        counts: list[int] = []
        for label in labels:
            variants = [variant for variant in prompts_per_label.get(label, []) if isinstance(variant, str) and variant]
            if not variants:
                variants = [prompt.format(label)]
            prompt_variants.extend(variants)
            counts.append(len(variants))
        if not prompt_variants:
            output_dim = getattr(model, "text_projection", None)
            dim = int(getattr(output_dim, "shape", [0, 0])[1]) if output_dim is not None else 0
            return np.zeros((0, dim), dtype="float32")
        with torch.no_grad():
            tokens = tokenizer(prompt_variants).to(device_resolved)
            feats = model.encode_text(tokens).detach().cpu().float().numpy()
        aggregated: list[np.ndarray] = []
        offset = 0
        for count in counts:
            segment = feats[offset : offset + count]
            offset += count
            aggregated.append(segment.mean(axis=0))
        return np.stack(aggregated, axis=0)

    prompts = [prompt.format(label) for label in labels]

    with torch.no_grad():
        tokens = tokenizer(prompts).to(device_resolved)
        feats = model.encode_text(tokens)
    return feats.detach().cpu().float().numpy()


__all__ = ["load_clip", "embed_images", "embed_labels"]
