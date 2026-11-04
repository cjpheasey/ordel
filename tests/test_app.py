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


def test_own_window_is_found_by_process_not_just_title():
    from studio_hub.app import pick_own_window
    windows = [(11, "Ordel", 500, "CabinetWClass"),                         # File Explorer open on dist\Ordel
               (22, "Ordel", 777, "WindowsForms10.Window.8.app.0.aec740"),  # Ordel itself
               (33, "Ordel", 777, "WindowsForms10.Window.8.app.0.x")]        # a hidden helper window of ours
    assert pick_own_window(windows, pid=777) == 22
    assert pick_own_window(windows[:1], pid=777) == 0


def test_saved_position_is_checked_in_screen_pixels(monkeypatch):
    import studio_hub.app as app
    asked = []
    monkeypatch.setattr(app, "_dpi_scale", lambda: 1.5)  # a 150% display
    monkeypatch.setattr(app.win32api, "MonitorFromPoint", lambda pt, flags: asked.append(pt) or 1)
    assert app.safe_geometry({"x": 1300, "y": 100, "width": 1200, "height": 780})["x"] == 1300
    assert asked == [(round((1300 + 40) * 1.5), round((100 + 20) * 1.5))]  # pywebview stores x/y unscaled
