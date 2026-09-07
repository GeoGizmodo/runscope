"""
RunScope demo: three modes on a hidden heavy-tail job (~30-60s of real CPU work).

  python demo_full.py 3     # Jedi   - samples the future, catches the hidden tail
  python demo_full.py 1     # Padawan - current-run only, under-estimates then reacts
  python demo_full.py 2     # Master  - run 4x to see history calibration kick in
  python demo_full.py       # all three, leading with Jedi

Run in a real terminal to see the live bar. The last 20% of items are secretly ~15x
slower than the rest, but every item looks the same up front - so a plain bar can't
see it coming. Jedi (measure mode) samples a little of the future and predicts it.
"""
import hashlib
import math
import sys
import time

import runscope


def cpu(iters):
    b = b"runscope-demo"
    x = 0.0
    for i in range(iters):
        b = hashlib.sha256(b).digest()
        x += math.sqrt((i % 97) + 1) * (b[0] + 1)
    return x


N = 300
LIGHT_ITERS = 30000
HEAVY_ITERS = 950000        # last 20% are ~15x slower (hidden behind identical size)


def make_items(n=N):
    cut = int(0.8 * n)
    return [{"id": i, "size": 1.0,
             "iters": LIGHT_ITERS if i < cut else HEAVY_ITERS} for i in range(n)]


ITEMS = make_items()
SIZE = lambda it: it["size"]


def measure_cost(it):
    t = time.perf_counter(); cpu(it["iters"]); return time.perf_counter() - t


def process(it):
    cpu(it["iters"])


def opt3():
    print("\n=== Jedi (measure=True) ===")
    key = f"demo_measure_{int(time.time())}"
    for it in runscope.track(ITEMS, key=key, label="images", weight=SIZE,
                             measure=True, measure_fn=measure_cost):
        process(it)


def opt1():
    print("\n=== Padawan (current run only) ===")
    key = f"demo_present_{int(time.time())}"
    for it in runscope.track(ITEMS, key=key, label="images", weight=SIZE,
                             prompt=False):
        process(it)


def opt2():
    print("\n=== Master (recurring job - run this option a few times) ===")
    key = "demo_history_recurring"
    for it in runscope.track(ITEMS, key=key, label="images", weight=SIZE,
                             prompt=False):
        process(it)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("3", "all"):
        opt3()
    if which in ("1", "all"):
        opt1()
    if which in ("2", "all"):
        opt2()
    print("\ndone.")
