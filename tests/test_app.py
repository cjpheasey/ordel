from studio_hub.app import safe_geometry


def test_minimised_or_offscreen_position_dropped():
    assert safe_geometry({"x": -32000, "y": -32000, "width": 160, "height": 28}) == {}
    assert safe_geometry({"x": 99999, "y": 99999, "width": 1200, "height": 780}) == {"width": 1200, "height": 780}


def test_onscreen_geometry_kept():
    assert safe_geometry({"x": 100, "y": 100, "width": 1200, "height": 780}) == {"x": 100, "y": 100, "width": 1200, "height": 780}


def test_missing_geometry():
    assert safe_geometry(None) == {}


def test_resizing_from_each_edge():
    from studio_hub.app import resized_rect
    start = (100, 100, 1300, 900)  # left, top, right, bottom
    assert resized_rect(start, 50, 0, "e", 900, 600) == (100, 100, 1350, 900)
    assert resized_rect(start, -50, 0, "w", 900, 600) == (50, 100, 1300, 900)
    assert resized_rect(start, 0, 40, "s", 900, 600) == (100, 100, 1300, 940)
    assert resized_rect(start, 0, -40, "n", 900, 600) == (100, 60, 1300, 900)
    assert resized_rect(start, 30, 20, "se", 900, 600) == (100, 100, 1330, 920)
    assert resized_rect(start, -30, -20, "nw", 900, 600) == (70, 80, 1300, 900)


def test_resizing_stops_at_the_minimum_size_without_moving_the_far_edge():
    from studio_hub.app import resized_rect
    start = (100, 100, 1300, 900)
    assert resized_rect(start, -1000, 0, "e", 900, 600) == (100, 100, 1000, 900)
    assert resized_rect(start, 1000, 1000, "nw", 900, 600) == (400, 300, 1300, 900)
