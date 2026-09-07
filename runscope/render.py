"""
runscope.render -- terminal progress bar (the primary front end).

Single-line live bar drawn to stdout with a carriage return, so it cannot stack on
any OS/terminal. Permanent event lines print via emit(); the bar re-pins next tick.
No decorative emojis. The Star Wars mode tag [Padawan]/[Jedi]/[Master] plus an honest
range/confidence are the only flavor/trust signals. Numbers come straight from the
validated tracker -- the renderer never invents or smooths a value.
"""
import os
import shutil
import sys
import time


def _enable_ansi():
    if os.name != "nt":
        return
    try:
        import ctypes
        k = ctypes.windll.kernel32
        for handle in (-11, -12):
            h = k.GetStdHandle(handle)
            mode = ctypes.c_uint()
            if k.GetConsoleMode(h, ctypes.byref(mode)):
                k.SetConsoleMode(h, mode.value | 0x0004)
    except Exception:
        pass


def _fmt_dur(sec):
    sec = max(0, int(round(sec)))
    if sec < 60:
        return f"{sec}s"
    if sec < 3600:
        return f"{sec // 60}m{sec % 60:02d}s"
    return f"{sec // 3600}h{(sec % 3600) // 60:02d}m"


def _fmt_clock(sec_from_now):
    t = time.localtime(time.time() + max(0, sec_from_now))
    s = time.strftime("%I:%M %p", t)
    return s[1:] if s.startswith("0") else s


def _bar(frac, width, uni):
    fill = int(round(max(0.0, min(1.0, frac)) * width))
    if uni:
        return "\u2588" * fill + "\u2591" * (width - fill)
    return "#" * fill + "-" * (width - fill)


_MODE_TAG = {"throughput": "Padawan", "measured": "Jedi", "history": "Master"}
_MODE_QUOTE = {
    "throughput": "Patience you must have.",
    "measured": "Your eyes can deceive you; do not trust them.",
    "history": "In my experience, there is no such thing as luck.",
}


class TerminalRenderer:
    """Single-line live progress renderer (stdout by default)."""

    def __init__(self, label="", stream=None, enabled=None, min_interval=0.08):
        self.label = label
        self.stream = stream or sys.stdout
        if enabled is None:
            try:
                enabled = self.stream.isatty()
            except Exception:
                enabled = False
        self.enabled = enabled
        self.min_interval = min_interval
        self._last_draw = 0.0
        self._active = False
        self._maxlen = 0
        enc = (getattr(self.stream, "encoding", None) or "").lower()
        self._uni = "utf" in enc
        if self.enabled:
            _enable_ansi()

    def _g(self, uni, ascii_):
        return uni if self._uni else ascii_

    def _line(self, est):
        cols = shutil.get_terminal_size((90, 20)).columns
        barw = max(8, min(22, cols - 60))
        pct = int(est.frac * 100) if est.total else 0
        cnt = f"{est.done}/{est.total}" if est.total else f"{est.done}"
        dot = self._g("\u00b7", "|")
        rng = self._g("\u2013", "-")
        lb = self._g("\u2595", "[")
        rb = self._g("\u258f", "]")
        warn = "revised " if est.revised_up else ""
        tag = _MODE_TAG.get(est.source, "")
        bar = _bar(est.frac, barw, self._uni)
        left = _fmt_dur(est.eta_remaining)
        rlo, rhi = _fmt_dur(est.range_lo), _fmt_dur(est.range_hi)
        return (f"{self.label} {lb}{bar}{rb} {pct:3d}% {cnt} {dot} "
                f"{warn}{left} left ({rlo}{rng}{rhi}) {dot} {est.confidence} "
                f"{dot} [{tag}]")

    def draw(self, est, force=False):
        if not self.enabled:
            return
        now = time.time()
        if not force and (now - self._last_draw) < self.min_interval:
            return
        self._last_draw = now
        line = self._line(est)
        self._maxlen = max(self._maxlen, len(line))
        self.stream.write("\r" + line.ljust(self._maxlen))
        self.stream.flush()
        self._active = True

    def emit(self, msg):
        if not self.enabled:
            self.stream.write(msg + "\n")
            self.stream.flush()
            return
        if self._active:
            self.stream.write("\r" + " " * self._maxlen + "\r")
            self._active = False
        self.stream.write(msg + "\n")
        self.stream.flush()

    def close(self, summary=None):
        if not self.enabled:
            if summary:
                self.stream.write(summary + "\n")
                self.stream.flush()
            return
        if self._active:
            self.stream.write("\r" + " " * self._maxlen + "\r")
            self._active = False
        if summary:
            self.stream.write(summary + "\n")
        self.stream.flush()
