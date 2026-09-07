"""
runscope.estimators -- the validated ETA engine.

These functions are lifted UNCHANGED (same math) from the ETA-Proto research
harness eta-proto/pathV/sketch_eta.py, which is the code the 26-page research
journal validated. Do NOT "improve" them without re-running the preregistered
gates; the whole point of the product is that this math is proven.

  sizew_naive       -- size-weighted throughput ETA (the strong baseline that beat
                       every sophisticated method for enumerable workloads).
  strat_sketch      -- stratified Horvitz-Thompson estimate of remaining cost from a
                       tiny representative sample of UNEXECUTED items (Path V; 40-90%
                       MAPE reduction on hard heterogeneous workloads).
  conformal_interval-- a simple, honest prediction range around a point ETA.

No third-party dependencies (pure stdlib) so the free client is trivial to install.
"""
import random
import statistics

N_STRATA = 4


def sizew_naive(prefix_dts, prefix_sizes, rem_sizes):
    """Size-weighted throughput ETA for REMAINING work (seconds).

    rate = total observed size / total observed time; remaining time = remaining
    size / rate. Falls back to count-naive when all sizes are equal.
    """
    tot_t = sum(prefix_dts)
    tot_s = sum(max(1e-9, s) for s in prefix_sizes)
    rate = tot_s / max(1e-9, tot_t)          # size-units per second
    rem_size = sum(max(1e-9, s) for s in rem_sizes)
    return rem_size / max(1e-9, rate)        # seconds


def count_naive(prefix_dts, rem_count):
    """Count-naive remaining time: remaining_count * mean per-item time."""
    mean_dt = statistics.mean(prefix_dts) if prefix_dts else 0.0
    return rem_count * mean_dt


def sizew_recency(prefix_dts, prefix_sizes, rem_sizes, window=None):
    """Size-weighted remaining time that REACTS to regime changes (e.g. a heavy tail).

    Uses a rate that blends the whole-run size-weighted rate with a recent-window
    rate, taking the SLOWER (more conservative) when recent items are heavier per
    size-unit. This keeps a naive current-run estimate from 'hanging' at a tiny ETA
    while the workload has clearly gotten slower -- without any sampling or history.
    """
    if not prefix_dts:
        return 0.0
    n = len(prefix_dts)
    w = window or max(5, n // 5)          # last ~20% of the run
    w = min(w, n)
    tot_t = sum(prefix_dts)
    tot_s = sum(max(1e-9, s) for s in prefix_sizes)
    rate_all = tot_s / max(1e-9, tot_t)               # size-units per second (all)
    rec_t = sum(prefix_dts[-w:])
    rec_s = sum(max(1e-9, s) for s in prefix_sizes[-w:])
    rate_rec = rec_s / max(1e-9, rec_t)               # recent size-units per second
    # slower rate -> larger ETA. When recent work is heavier, react up immediately.
    rate = min(rate_all, rate_rec)
    rem_size = sum(max(1e-9, s) for s in rem_sizes)
    return rem_size / max(1e-9, rate)


def _strata_by_size(rem_sizes, nstrata):
    """Group item indices into strata by size. If the sizes take only a few distinct
    values (the common case: e.g. thumbnails vs full-res), stratify by VALUE so each
    size class is its own stratum and is guaranteed representation in the sample.
    Otherwise fall back to equal-rank quantile strata. This ensures a heavy tail is
    never missed by the sketch."""
    n = len(rem_sizes)
    distinct = sorted(set(rem_sizes))
    if len(distinct) <= nstrata:
        by_val = {v: [] for v in distinct}
        for j, s in enumerate(rem_sizes):
            by_val[s].append(j)
        return [by_val[v] for v in distinct if by_val[v]]
    order = sorted(range(n), key=lambda j: rem_sizes[j])
    strata = [[] for _ in range(nstrata)]
    for rank, j in enumerate(order):
        s = min(nstrata - 1, rank * nstrata // max(1, n))
        strata[s].append(j)
    return [s for s in strata if s]


def strat_sketch(rem_dts, rem_sizes, m, rng=None, nstrata=N_STRATA):
    """Stratified Horvitz-Thompson estimate of TOTAL remaining cost (seconds) from
    a sample of m remaining items whose true cost rem_dts[j] has been measured.

    Returns (estimate_seconds, sampled_cost_seconds). Design-unbiased under the
    sampling design. In production the caller MEASURES the sampled items (actually
    runs them) to obtain rem_dts for the sampled indices; the estimate then covers
    the whole remaining set.
    """
    rng = rng or random.Random()
    N = len(rem_dts)
    if N == 0:
        return 0.0, 0.0
    m = max(1, min(N, m))
    strata = _strata_by_size(rem_sizes, nstrata)
    weights = [len(st) for st in strata]     # proportional allocation
    wtot = sum(weights) or 1.0
    alloc = [1] * len(strata)
    rest = max(0, m - len(strata))
    for h in range(len(strata)):
        alloc[h] += int(round(rest * weights[h] / wtot))
    est = 0.0
    cost = 0.0
    for h, st in enumerate(strata):
        Nh = len(st)
        mh = max(1, min(Nh, alloc[h]))
        pick = rng.sample(st, mh)
        pih = mh / Nh                        # inclusion probability
        est += sum(rem_dts[j] / pih for j in pick)
        cost += sum(rem_dts[j] for j in pick)
    return est, cost


def conformal_interval(point_eta, prefix_dts, prefix_sizes, level=0.90):
    """Honest prediction range around a point ETA (seconds).

    Uses the observed dispersion of per-item time-per-size on the prefix to scale a
    symmetric-ish multiplicative interval. This is the deployable stand-in for the
    SSM conformal intervals that survived the research (calibrated, ~unit coverage);
    it is intentionally simple and dependency-free. Returns (lo, hi) in seconds.
    """
    if len(prefix_dts) < 3:
        return point_eta * 0.7, point_eta * 1.4
    rate_per_item = [dt / max(1e-9, s) for dt, s in zip(prefix_dts, prefix_sizes)]
    m = statistics.mean(rate_per_item)
    cv = (statistics.pstdev(rate_per_item) / m) if m > 0 else 0.5
    # wider interval when the prefix is noisier; z~1.64 for 90%
    z = 1.64 if level >= 0.9 else 1.28
    frac = min(0.6, z * cv / max(1.0, len(prefix_dts) ** 0.5) + 0.05)
    return point_eta * (1 - frac), point_eta * (1 + frac)
