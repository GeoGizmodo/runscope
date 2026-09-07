"""
RunScope accuracy across workload shapes. Shows, for each shape, what a plain
count-based ETA predicts at 20% done vs what RunScope predicts vs the actual time.

  python demo_shapes.py

Every item reports the same size, so the cost is HIDDEN from a plain bar - only
sampling the future (Jedi) reveals it. Uses real CPU work.
"""
import hashlib
import math
import random
import time

import runscope
from runscope.tracker import Tracker


def cpu(iters):
    b = b"runscope-shapes"
    x = 0.0
    for i in range(iters):
        b = hashlib.sha256(b).digest()
        x += math.sqrt((i % 97) + 1) * (b[0] + 1)
    return x


BASE = 20000
N = 120


def items_for(mults):
    return [{"id": i, "size": 1.0, "iters": int(BASE * m)} for i, m in enumerate(mults)]


def shapes():
    rng = random.Random(7)
    return {
        "heavy-tail": [1 if i < int(0.8 * N) else 12 for i in range(N)],
        "heavy-middle": [12 if int(0.4 * N) <= i < int(0.6 * N) else 1 for i in range(N)],
        "heavy-front": [12 if i < int(0.2 * N) else 1 for i in range(N)],
        "uniform": [3] * N,
        "random-spikes": [15 if rng.random() < 0.10 else 1 for i in range(N)],
    }


def measure_cost(it):
    t = time.perf_counter(); cpu(it["iters"]); return time.perf_counter() - t


def dumb_and_runscope(mults):
    items = items_for(mults)
    n = len(items)
    true = [measure_cost(it) for it in items]
    true_total = sum(true)
    dec = int(0.20 * n)
    elapsed_at = sum(true[:dec])
    rate = dec / max(1e-9, elapsed_at)
    dumb_total = elapsed_at + (n - dec) / rate
    tr = Tracker(total=n, sizes=[1.0] * n, workflow_key="s" + str(random.random()))
    tr.apply_sample({j: true[j] for j in tr.sample_plan_full()})
    for i in range(dec):
        tr._dts.append(true[i]); tr._last = tr._start + sum(tr._dts)
        tr._done_sizes.append(1.0)
    est = tr.estimate()
    rs_total = elapsed_at + est.eta_remaining
    return (true_total, dumb_total, abs(dumb_total - true_total) / true_total * 100,
            rs_total, abs(rs_total - true_total) / true_total * 100)


def main():
    print("ACCURACY BY WORKLOAD SHAPE (prediction at 20% done)\n")
    print(f"{'shape':<15}{'actual':>8}{'plain bar':>11}{'off':>6}{'RunScope':>10}{'off':>6}")
    for name, mults in shapes().items():
        tt, dt, de, rt, re = dumb_and_runscope(mults)
        print(f"{name:<15}{tt:7.1f}s{dt:10.1f}s{de:5.0f}%{rt:9.1f}s{re:5.0f}%")


if __name__ == "__main__":
    main()
