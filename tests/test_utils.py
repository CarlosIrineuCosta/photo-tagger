import math
from datetime import datetime

from app import utils


def test_sha1_file(tmp_path):
    target = tmp_path / "hello.txt"
    target.write_text("hello world", encoding="utf-8")
    # precomputed with `sha1("hello world")`
    assert utils.sha1_file(str(target)) == "2aae6c35c94fcfb415dbe95f408b9ce91ee846ed"


def test_chunked_even_and_remainder():
    data = list(range(7))
    chunks = list(utils.chunked(data, 3))
    assert chunks == [data[0:3], data[3:6], data[6:7]]


def test_path_date_tokens_extracts_multiple_components():
    path = "/photos/2023-07-15_trip/IMG_20230716_120000.jpg"
    tokens = utils.path_date_tokens(path)
    assert any(token.startswith("2023") for token in tokens)
    assert isinstance(tokens, list) and tokens


def test_safe_datetime_parse_accepts_common_formats():
    raw = "2021:12:31 23:59:59\n"
    parsed = utils.safe_datetime_parse(raw)
    assert isinstance(parsed, datetime)
    assert parsed.year == 2021 and parsed.month == 12 and parsed.day == 31


def test_safe_datetime_parse_returns_none_for_invalid():
    assert utils.safe_datetime_parse("not a date") is None
    assert utils.safe_datetime_parse("") is None


def test_mean_handles_iterables_and_empty():
    assert math.isclose(utils.mean([1, 2, 3, 4]), 2.5)
    assert utils.mean([]) == 0.0


def test_normalize_scales_vector_and_handles_zero():
    vec = (3.0, 4.0, 0.0)
    normalized = utils.normalize(vec)
    assert math.isclose(sum(v * v for v in normalized), 1.0, rel_tol=1e-5)

    zero = (0.0, 0.0, 0.0)
    assert utils.normalize(zero) == zero
