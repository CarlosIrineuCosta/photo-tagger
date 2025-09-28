from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np
import torch
from PIL import Image

import open_clip

try:
    from transformers import BlipForConditionalGeneration, BlipProcessor
except Exception:  # pragma: no cover - optional heavy deps
    BlipForConditionalGeneration = None
    BlipProcessor = None

try:
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None

_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
_BLIP = None
_BLIP_P = None
_CLIP = None
_CLIP_PREPROCESS = None
_CLIP_TOKENIZER = None


@dataclass
class AiTagConfig:
    max_ai_tags: int = 12
    ai_prefix: str = "AI:"
    concept_bank_extra: Sequence[str] = ()
    city_whitelist: Sequence[str] = ()
    ocr_enable: bool = False
    ocr_min_conf: float = 0.75
    clip_model: str = "ViT-L-14"
    clip_pretrained: str = "openai"
    clip_device: str = _DEVICE
    blip_model: str = "Salesforce/blip-image-captioning-large"


def _load_blip(model_name: str):
    global _BLIP, _BLIP_P
    if BlipForConditionalGeneration is None or BlipProcessor is None:
        raise RuntimeError("transformers[BLIP] not installed")
    if _BLIP is None:
        _BLIP_P = BlipProcessor.from_pretrained(model_name)
        _BLIP = BlipForConditionalGeneration.from_pretrained(model_name)
        _BLIP.to(_DEVICE)
        _BLIP.eval()


def _load_clip(clip_model: str, pretrained: str, device: str):
    global _CLIP, _CLIP_PREPROCESS, _CLIP_TOKENIZER
    if _CLIP is None:
        model, _, preprocess = open_clip.create_model_and_transforms(clip_model, pretrained=pretrained, device=device)
        tokenizer = open_clip.get_tokenizer(clip_model)
        model.eval()
        _CLIP = model
        _CLIP_PREPROCESS = preprocess
        _CLIP_TOKENIZER = tokenizer


_WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-&']+")
_STOP = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "in",
    "on",
    "at",
    "with",
    "for",
    "by",
    "to",
    "from",
    "this",
    "that",
    "these",
    "those",
    "its",
    "it",
    "is",
    "are",
    "was",
    "were",
    "be",
    "being",
    "been",
}


def _clean_tokens(text: str) -> List[str]:
    tokens = [tok.lower() for tok in _WORD_RE.findall(text)]
    return [tok for tok in tokens if tok not in _STOP and len(tok) > 2]


def _ngram(tokens: List[str], nmin: int = 1, nmax: int = 2) -> List[str]:
    grams: List[str] = []
    for n in range(nmin, nmax + 1):
        for i in range(0, len(tokens) - n + 1):
            grams.append(" ".join(tokens[i : i + n]))
    return grams


def _dedupe(seq: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _read_image(path: str) -> Image.Image:
    return Image.open(path).convert("RGB")


def blip_caption(path: str, model_name: str) -> str:
    _load_blip(model_name)
    image = _read_image(path)
    inputs = _BLIP_P(images=image, return_tensors="pt").to(_DEVICE)
    with torch.no_grad():
        output = _BLIP.generate(**inputs, max_new_tokens=40)
    caption = _BLIP_P.decode(output[0], skip_special_tokens=True)
    return caption.strip()


def ocr_tokens(path: str, min_conf: float = 0.75) -> List[str]:
    if pytesseract is None:
        return []
    image = _read_image(path)
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    tokens: List[str] = []
    for word, conf in zip(data.get("text", []), data.get("conf", [])):
        try:
            conf_val = float(conf) / 100.0
        except Exception:
            continue
        if conf_val < min_conf:
            continue
        word = word.strip().lower()
        if len(word) < 3:
            continue
        if _WORD_RE.fullmatch(word):
            tokens.append(word)
    return _dedupe(tokens)


def mine_concepts_from_caption(
    caption: str,
    extra_bank: Iterable[str] = (),
    city_whitelist: Iterable[str] = (),
    limit: int = 64,
) -> List[str]:
    tokens = _clean_tokens(caption)
    grams = _ngram(tokens, 1, 2)
    extras = [w.lower() for w in extra_bank]
    cities = [w.lower() for w in city_whitelist]
    candidates = _dedupe(extras + cities + grams)
    junk = {"photo", "image", "picture"}
    candidates = [c for c in candidates if 3 <= len(c) <= 32 and c not in junk]
    return candidates[:limit]


def score_concepts_with_clip(
    image_embedding: np.ndarray,
    concepts: Sequence[str],
    clip_model: str,
    pretrained: str,
    device: str,
) -> List[Tuple[str, float]]:
    _load_clip(clip_model, pretrained, device)
    img = torch.tensor(image_embedding, device=device, dtype=torch.float32)
    if img.ndim == 1:
        img = img[None, :]
    img = img / (img.norm(dim=-1, keepdim=True) + 1e-6)
    prompts = [f"a photo of {c}" for c in concepts]
    tokens = _CLIP_TOKENIZER(prompts).to(device)
    with torch.no_grad():
        text = _CLIP.encode_text(tokens)
        text = text / (text.norm(dim=-1, keepdim=True) + 1e-6)
        sims = (img @ text.T).float().cpu().numpy().ravel()
    pairs = list(zip(concepts, sims.tolist()))
    pairs.sort(key=lambda it: it[1], reverse=True)
    return pairs


def ai_tags_local(proxy_path: str, image_embedding: np.ndarray, cfg: AiTagConfig) -> List[str]:
    caption = ""
    if BlipForConditionalGeneration is not None:
        try:
            caption = blip_caption(proxy_path, cfg.blip_model)
        except Exception:
            caption = ""
    concepts = mine_concepts_from_caption(caption, cfg.concept_bank_extra, cfg.city_whitelist)
    if cfg.ocr_enable:
        concepts.extend(ocr_tokens(proxy_path, cfg.ocr_min_conf))
    concepts = _dedupe(concepts)
    if not concepts:
        return []
    scored = score_concepts_with_clip(
        image_embedding=image_embedding,
        concepts=concepts,
        clip_model=cfg.clip_model,
        pretrained=cfg.clip_pretrained,
        device=cfg.clip_device if torch.cuda.is_available() else "cpu",
    )
    top = [concept for concept, _ in scored[: cfg.max_ai_tags]]
    return [f"{cfg.ai_prefix}{concept}" for concept in top]


__all__ = ["AiTagConfig", "ai_tags_local"]
