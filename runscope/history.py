"""
runscope.history -- the "Past" layer (local store; cloud sync is optional/Pro).

Design (validated by ETA-Proto Path W): LOG EVERY RUN, but only CALIBRATE once a
workflow has >= MIN_RUNS prior runs. Before that, behave as Present-only (do no
harm). Calibration factor k_w = median(actual_total / naive_eta_at_decision) over
prior runs of the SAME workflow key. Methodology is never surfaced.

Workflow identity: a stable key derived from the call site (script path + line) and
an item-count bucket, or an explicit user-provided key. Wrong keys are the main risk,
so an explicit key= is always recommended for recurring jobs.
"""
import hashlib
import json
import os
import statistics
import time

from .config import HOME as _STORE

MIN_RUNS = 3          # dormant below this (Path W: converges by ~5)


def _path(key):
    os.makedirs(_STORE, exist_ok=True)
    safe = hashlib.sha1(key.encode()).hexdigest()[:16]
    return os.path.join(_STORE, f"wf_{safe}.json")


def default_key(script=None, extra=None, n=None):
    """Stable workflow key from call site + item-count bucket."""
    base = script or "unknown"
    bucket = ""
    if n:
        # bucket by order of magnitude so different-sized runs of the same job match
        import math
        bucket = f"~1e{int(math.log10(max(1, n)))}"
    raw = f"{base}|{extra or ''}|{bucket}"
    return raw


def load(key):
    p = _path(key)
    if not os.path.exists(p):
        return {"key": key, "runs": []}
    try:
        return json.load(open(p))
    except Exception:
        return {"key": key, "runs": []}


def calibration(key):
    """Return (k_w, confidence). Dormant (1.0, 'low') until MIN_RUNS prior runs."""
    data = load(key)
    ratios = [r["ratio"] for r in data["runs"] if r.get("ratio")]
    if len(ratios) < MIN_RUNS:
        return 1.0, "low"
    k = statistics.median(ratios)
    cv = (statistics.pstdev(ratios) / k) if k > 0 and len(ratios) > 1 else 1.0
    conf = "high" if (len(ratios) >= 5 and cv < 0.15) else "medium"
    return k, conf


def n_runs(key):
    """How many prior runs are recorded for this workflow key."""
    return len(load(key).get("runs", []))


def record(key, naive_eta_at_decision, actual_total, meta=None):
    """Append one completed run's calibration observation."""
    if not naive_eta_at_decision or naive_eta_at_decision <= 0:
        return
    data = load(key)
    data["runs"].append({
        "ts": time.time(),
        "ratio": actual_total / naive_eta_at_decision,
        "naive_eta": naive_eta_at_decision,
        "actual": actual_total,
        "meta": meta or {},
    })
    data["runs"] = data["runs"][-100:]        # cap local history
    json.dump(data, open(_path(key), "w"))
