import pytest

from studio_hub.hotkey import HotkeyListener, parse_hotkey

TEST_COMBO = "Ctrl+Alt+Shift+F23"  # nothing else should be using this


def test_parse_default():
    assert parse_hotkey("Ctrl+Shift+Space") == (0x2 | 0x4 | 0x4000, 0x20)


def test_parse_letters_function_keys_and_case():
    assert parse_hotkey("alt+k") == (0x1 | 0x4000, ord("K"))
    assert parse_hotkey("Win+F5")[1] == 0x74


@pytest.mark.parametrize("combo", ["", "Ctrl+", "Ctrl+Banana", "Shift", "Ctrl+A+B"])
def test_parse_rejects_garbage(combo):
    with pytest.raises(ValueError):
        parse_hotkey(combo)


def test_register_and_stop():
    listener = HotkeyListener(lambda: None)
    try:
        assert listener.register(TEST_COMBO) is True
    finally:
        listener.stop()


def test_register_failure_reports_false():
    first, second = HotkeyListener(lambda: None), HotkeyListener(lambda: None)
    try:
        assert first.register(TEST_COMBO) is True
        assert second.register(TEST_COMBO) is False
    finally:
        first.stop()
        second.stop()


def test_reregister_frees_old_combo():
    listener, other = HotkeyListener(lambda: None), HotkeyListener(lambda: None)
    try:
        listener.register(TEST_COMBO)
        listener.register("Ctrl+Alt+Shift+F22")
        assert other.register(TEST_COMBO) is True
    finally:
        listener.stop()
        other.stop()
