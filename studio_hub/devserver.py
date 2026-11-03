"""Serve the real UI and API without a window, for checking the interface in a browser.

python -m studio_hub.devserver [port]
"""
import sys

from .api import Api
from .bridge import ReaperBridge
from .capture import CaptureRunner
from .helper import HelperCapture
from .library import Library
from .paths import bridge_dir, data_dir, reaper_dir, resource, snapshots_dir
from .server import make_server


def main() -> None:
    library = Library(data_dir() / "library.json")
    bridge = ReaperBridge(bridge_dir())
    api = None
    capture = CaptureRunner(bridge, library, snapshots_dir(), lambda: api.plugins, helper=HelperCapture(reaper_dir()))
    noop = lambda *a: None
    api = Api(reaper_dir(), library, bridge, capture,
              {"hide": noop, "minimize": noop, "quit": noop, "pick_image": noop, "set_hotkey": lambda c: True})
    server = make_server(api, resource("ui"), snapshots_dir(), int(sys.argv[1]) if len(sys.argv) > 1 else 0)
    print(f"http://127.0.0.1:{server.server_address[1]}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
