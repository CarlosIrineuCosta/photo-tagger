from app import heuristics


def test_studio_black_vs_night_adds_tags_when_conditions_met():
    cfg = {
        "enable": True,
        "dark_ratio": 0.6,
        "iso_threshold": 800,
        "face_required_for_studio": True,
    }
    exif = {"iso": 100, "exposure_time": 1 / 125}
    proxy = {"dark_ratio": 0.7}

    result = heuristics.studio_black_vs_night(exif, proxy, cfg, has_person=True)

    assert "CK:studio" in result["add"]
    assert "CK:black-background" in result["add"]
    assert "CK:night" in result["suppress"]


def test_studio_black_vs_night_requires_face_when_configured():
    cfg = {
        "enable": True,
        "dark_ratio": 0.6,
        "iso_threshold": 800,
        "face_required_for_studio": True,
    }
    exif = {"iso": 200, "exposure_time": 1 / 125}
    proxy = {"dark_ratio": 0.75}

    result = heuristics.studio_black_vs_night(exif, proxy, cfg, has_person=False)

    assert result == {"add": [], "suppress": []}


def test_studio_black_vs_night_returns_empty_when_disabled():
    cfg = {"enable": False}
    result = heuristics.studio_black_vs_night({}, {}, cfg, has_person=True)
    assert result == {"add": [], "suppress": []}


def test_suppress_hand_on_nude():
    assert heuristics.suppress_hand_on_nude(True, True) is True
    assert heuristics.suppress_hand_on_nude(True, False) is False
    assert heuristics.suppress_hand_on_nude(False, True) is False
