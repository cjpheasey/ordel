from studio_hub.categories import CATEGORIES, resolve_category


def test_reaper_tag_wins():
    assert resolve_category(["Distortion"], "Comp X", False) == "saturation"


def test_multi_tag_first_mapped():
    assert resolve_category(["OnlyARA", "EQ", "Dynamics"], "x", False) == "eq"


def test_instrument_tag_with_prefix():
    assert resolve_category(["Instrument Drum Sampler"], "Sitala", True) == "instruments"


def test_instrument_fallback():
    assert resolve_category([], "Weird Name", True) == "instruments"


def test_unmapped_tag_falls_back_to_name():
    assert resolve_category(["Vocals"], "Nectar 4 Gate", False) == "dynamics"


def test_name_keyword_fallback():
    assert resolve_category([], "Bus Compressor", False) == "dynamics"


def test_no_false_keyword_hit():
    assert resolve_category([], "Ampersand Space", False) == "uncategorised"


def test_every_category_has_color_and_uncategorised_last():
    assert all(c["color"].startswith("#") for c in CATEGORIES)
    assert CATEGORIES[-1]["key"] == "uncategorised" and len({c["key"] for c in CATEGORIES}) == 16
