"""Stands in for the Lua bridge running inside REAPER."""
import os
import threading
import time
from pathlib import Path


class FakeReaper:
    def __init__(self, bridge_dir: Path, replies: dict[str, str] | None = None, die_on: str | None = None,
                 stall_after_open: float = 0.0, delays: dict[str, float] | None = None):
        self.dir = Path(bridge_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.replies = replies or {}
        self.delays = delays or {}
        self.received: list[tuple[str, str]] = []
        self.die_on = die_on  # simulate REAPER crashing when this plugin is opened
        self.dead = False
        self.stall_after_open = stall_after_open  # seconds of silence after CAPTURE_OPEN
        self._quiet_until = 0.0
        self._stop = threading.Event()
        (self.dir / "heartbeat.txt").write_text("1")
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        cmd = self.dir / "command.txt"
        while not self._stop.is_set():
            if self.dead or time.time() < self._quiet_until:
                time.sleep(0.02)
                continue
            (self.dir / "heartbeat.txt").write_text(str(time.time()))
            if cmd.exists():
                cid, verb, arg = cmd.read_text(encoding="utf-8").rstrip("\n").split("\t", 2)
                cmd.unlink()
                self.received.append((verb, arg))
                if self.die_on and verb == "CAPTURE_OPEN" and self.die_on in arg:
                    self.dead = True
                    continue
                reply = self.replies.get(verb, "OK")
                if callable(reply):  # depends on what was asked
                    reply = reply(arg)
                if isinstance(reply, list):  # one reply per call; the last one repeats
                    reply = reply.pop(0) if len(reply) > 1 else reply[0]
                if verb in self.delays:  # busy inside REAPER, e.g. a heavy plugin loading
                    time.sleep(self.delays[verb])
                tmp = self.dir / "response.tmp"
                tmp.write_text(f"{cid}\t{reply}\t".rstrip("\t") + "\n", encoding="utf-8")
                os.replace(tmp, self.dir / "response.txt")
                if verb == "CAPTURE_OPEN" and self.stall_after_open:
                    self._quiet_until = time.time() + self.stall_after_open
                    old = time.time() - 60
                    os.utime(self.dir / "heartbeat.txt", (old, old))  # looks exactly like REAPER going silent
            time.sleep(0.02)

    def stop(self):
        self._stop.set()
        self._thread.join()
