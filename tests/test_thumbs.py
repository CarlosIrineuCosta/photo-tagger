import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from app.core import thumbs

# Sample XMP content with an exposure setting
XMP_CONTENT = """
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core 5.6-c140 79.160451, 2017/05/06-01:08:21        ">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:crs="http://ns.adobe.com/crs/1.0/"
   crs:Exposure2012="+1.50"/>
 </rdf:RDF>
</x:xmpmeta>
"""

@pytest.fixture
def mock_rawpy():
    with patch("app.core.thumbs.rawpy", MagicMock()) as mock_rawpy:
        mock_raw = MagicMock()
        mock_rawpy.imread.return_value.__enter__.return_value = mock_raw
        # Make fromarray return a mock image with a size attribute
        mock_image = MagicMock()
        mock_image.size = (100, 100)
        mock_image.convert.return_value = mock_image
        with patch("app.core.thumbs.Image.fromarray", return_value=mock_image):
            yield mock_rawpy

def test_build_thumbnail_with_xmp(tmp_path: Path, mock_rawpy):
    """
    Verify that RAW thumbnails are processed with XMP adjustments.
    """
    # Setup paths and files
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    raw_path = image_dir / "test.nef"
    raw_path.touch()
    xmp_path = image_dir / "test.xmp"
    xmp_path.write_text(XMP_CONTENT)

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    
    config_path = tmp_path / "config.yaml"
    config_path.write_text("""
thumbnails:
  xmp_processing: true
  xmp_cache_dir: "xmp_cache"
""")

    # Call the function
    thumbs.build_thumbnail(
        image_path=raw_path,
        cache_root=cache_dir,
        config_path=str(config_path)
    )

    # Assertions
    mock_rawpy.imread.assert_called_once_with(str(raw_path))
    mock_raw = mock_rawpy.imread.return_value.__enter__.return_value
    
    # Check that postprocess was called with brightness adjustment
    call_args, call_kwargs = mock_raw.postprocess.call_args
    assert "bright" in call_kwargs
    # exposure = +1.5, so bright = 2**1.5 = 2.828...
    assert call_kwargs["bright"] == pytest.approx(2 ** 1.5)
    assert call_kwargs["no_auto_bright"] is False
