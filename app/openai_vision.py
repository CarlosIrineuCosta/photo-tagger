from __future__ import annotations

import base64
import json
from io import BytesIO
from typing import List, Sequence

from PIL import Image

SYSTEM_PROMPT = """You are a photo tagger. Respond ONLY with a compact JSON array of lowercase tags.
* Prefer nouns and short attributes (e.g., "blue glass", "statue", "venice", "bridge", "overcast").
* Use at most {max_tags} tags.
* Do not include words like "photo" or "image".
* Use a city name ONLY if there is clear signage or a distinctive landmark that appears in the provided whitelist.
* No explanations. JSON array only.
"""

USER_PROMPT = """Cities you may use if appropriate (whitelist):
{city_list}
Examples: ["ai:car","ai:monument","ai:venice","ai:glass","ai:blue glass","ai:sunny day","ai:reflection","ai:cathedral","ai:graffiti"]
Return tags prefixed with "ai:" and keep them short.
"""


def _b64_png(path: str) -> str:
    image = Image.open(path).convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def call_openai_vision_on_image(
    image_path: str,
    city_whitelist: Sequence[str],
    max_tags: int = 12,
    model: str = "gpt-4o-mini",
) -> List[str]:
    import os

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    sys_prompt = SYSTEM_PROMPT.format(max_tags=max_tags)
    usr_prompt = USER_PROMPT.format(city_list=", ".join(city_whitelist))
    img_b64 = _b64_png(image_path)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": [{"type": "text", "text": sys_prompt}]},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": usr_prompt},
                        {"type": "input_image", "image_data": img_b64},
                    ],
                },
            ],
            temperature=0.2,
        )
        text = response.output_text
    except Exception:
        import openai  # type: ignore

        openai.api_key = api_key
        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": sys_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": usr_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                    ],
                },
            ],
            temperature=0.2,
        )
        text = response["choices"][0]["message"]["content"]

    return _parse_tag_response(text, max_tags)


def _parse_tag_response(text: str, max_tags: int) -> List[str]:
    try:
        arr = json.loads(text)
        if isinstance(arr, list):
            return _normalize_tags(arr, max_tags)
    except Exception:
        pass

    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            arr = json.loads(text[start : end + 1])
            return _normalize_tags(arr, max_tags)
        except Exception:
            return []
    return []


def _normalize_tags(arr, max_tags: int) -> List[str]:
    tags: List[str] = []
    seen = set()
    for item in arr:
        token = str(item).strip().lower()
        if not token:
            continue
        if not token.startswith("ai:"):
            token = f"ai:{token}"
        if token in seen:
            continue
        seen.add(token)
        tags.append(token)
        if len(tags) >= max_tags:
            break
    return tags


__all__ = ["call_openai_vision_on_image"]
