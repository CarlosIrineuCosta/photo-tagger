from __future__ import annotations

from typing import Dict, List


def studio_black_vs_night(
    exif_meta: Dict,
    proxy_meta: Dict,
    config: Dict,
    has_person: bool,
    prefix: str = "CK:",
) -> Dict[str, List[str]]:
    result = {"add": [], "suppress": []}
    if not config.get("enable", True):
        return result

    dark_ratio = proxy_meta.get("dark_ratio", 0.0)
    iso_threshold = config.get("iso_threshold", 800)
    face_required = config.get("face_required_for_studio", True)

    iso = exif_meta.get("iso") or 0
    exposure_time = exif_meta.get("exposure_time") or 0.0
    # treat typical studio shutters approx 1/200 .. 1/30 seconds
    shutter_ok = 0 < exposure_time <= (1 / 30) and exposure_time >= (1 / 200)

    if dark_ratio >= config.get("dark_ratio", 0.65) and iso <= iso_threshold:
        if not face_required or has_person:
            if shutter_ok or iso <= iso_threshold:
                studio_tag = f"{prefix}studio"
                black_tag = f"{prefix}black-background"
                night_tag = f"{prefix}night"
                for tag in (studio_tag, black_tag):
                    if tag not in result["add"]:
                        result["add"].append(tag)
                if night_tag not in result["suppress"]:
                    result["suppress"].append(night_tag)
    return result


def suppress_hand_on_nude(is_people: bool, is_nude: bool) -> bool:
    return bool(is_people and is_nude)


__all__ = ["studio_black_vs_night", "suppress_hand_on_nude"]
