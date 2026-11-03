from studio_hub.app import safe_geometry


def test_minimised_or_offscreen_position_dropped():
    assert safe_geometry({"x": -32000, "y": -32000, "width": 160, "height": 28}) == {}
    assert safe_geometry({"x": 99999, "y": 99999, "width": 1200, "height": 780}) == {"width": 1200, "height": 780}


def test_onscreen_geometry_kept():
    assert safe_geometry({"x": 100, "y": 100, "width": 1200, "height": 780}) == {"x": 100, "y": 100, "width": 1200, "height": 780}


def test_missing_geometry():
    assert safe_geometry(None) == {}
