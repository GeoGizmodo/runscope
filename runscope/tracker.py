"""
runscope.tracker -- the run state machine (engine, no front-end).

Ingests per-item completions, computes the ETA via the validated estimators, blends
in historical calibration (the "Past" layer) when it is ready, and can invoke the
future-work sketch. Emits an immutable EtaEstimate that any SINK (terminal bar, log,
callback, cloud) can render. The methodology is NEVER named in user-facing fields.
"""
import time
from dataclasses import dataclass
from typing import Optional, List

from . import estimators as E


@dataclass
class EtaEstimate:
    done: int
    total: Optional[int]
    frac: float
    elapsed: float
    eta_remaining: float          # seconds remaining (best estimate)
    range_lo: float               # seconds remaining, low
    range_hi: float               # seconds remaining, high
    confidence: str               # "low" | "medium" | "high"
    source: str                   # internal tag: "throughput"|"history"|"measured"
    revised_up: bool = False      # sketch/history revised ETA materially upward
    note: str = ""                # plain-language, no methodology names


class Tracker:
    """Feed it item sizes up front (if known) and per-item completion times.

    sizes: optional list of per-item observable sizes (known before execution). If
    provided, unlocks size-weighting, honest ranges, and the future sketch. If not,
    the tracker assumes remaining items resemble completed ones (weaker).
    """

    def __init__(self, total=None, sizes: Optional[List[float]] = None,
                 workflow_key: Optional[str] = None, calibration: float = 1.0,
                 calibration_conf: str = "low"):
        self.total = total if total is not None else (len(sizes) if sizes else None)
        self.sizes = list(sizes) if sizes else None
        self.workflow_key = workflow_key
        self.calibration = calibration          # k_w from history (1.0 = none)
        self.calibration_conf = calibration_conf
        self._dts: List[float] = []
        self._done_sizes: List[float] = []
        self._start = time.perf_counter()
        self._last = self._start
        self._sample_costs = None      # {item_index: measured_seconds} from sketch
        self._sketch_note: str = ""

    def _size_of(self, idx):
        if self.sizes and idx < len(self.sizes):
            return max(1e-9, self.sizes[idx])
        return 1.0

    def update(self, idx=None) -> None:
        """Record completion of one item (call once per iteration)."""
        now = time.perf_counter()
        self._dts.append(now - self._last)
        self._last = now
        i = idx if idx is not None else (len(self._dts) - 1)
        self._done_sizes.append(self._size_of(i))

    @property
    def elapsed(self):
        return self._last - self._start

    def _remaining_sizes(self):
        done = len(self._dts)
        if self.sizes:
            return [max(1e-9, s) for s in self.sizes[done:]]
        # unknown: assume remaining items resemble the mean observed size
        rem_ct = (self.total - done) if self.total else 0
        avg = (sum(self._done_sizes) / len(self._done_sizes)) if self._done_sizes else 1.0
        return [avg] * max(0, rem_ct)

    def estimate(self) -> EtaEstimate:
        done = len(self._dts)
        total = self.total
        frac = (done / total) if total else 0.0
        elapsed = self.elapsed
        rem_sizes = self._remaining_sizes()

        if done == 0 or not rem_sizes:
            return EtaEstimate(done, total, frac, elapsed, 0.0, 0.0, 0.0,
                               "low", "throughput")

        # Present baseline -- recency-aware so a naive estimate REACTS to a regime
        # change (heavy tail) instead of hanging at a stale tiny ETA. This is still
        # pure current-run info (no sampling, no history).
        present_rem = E.sizew_recency(self._dts, self._done_sizes, rem_sizes)
        revised_up = False

        # ---- ONE model decides the estimate, in priority order ----
        if self._sample_costs is not None:
            # Future sketch. Estimate remaining time from the sampled items that are
            # STILL AHEAD of the cursor: their mean cost projects the cost of each
            # not-yet-run item. This tracks the tail's POSITION -- it stays high while
            # heavy sampled items are ahead and drops once we pass them -- instead of
            # using a flat whole-job average (which under-estimates mid-run). Falls
            # back to the overall sample mean if none are ahead yet.
            ahead = [c for j, c in self._sample_costs.items() if j >= done]
            if ahead:
                mean_ahead = sum(ahead) / len(ahead)
            else:
                mean_ahead = sum(self._sample_costs.values()) / len(self._sample_costs)
            n_rem = (total - done) if total else len(rem_sizes)
            base_rem = mean_ahead * n_rem
            source = "measured"
            if (elapsed + base_rem) > (elapsed + present_rem) * 1.25:
                revised_up = True
        elif abs(self.calibration - 1.0) > 1e-6:
            # Past: one model -- size-weighted prefix scaled by learned calibration.
            base_rem = present_rem * self.calibration
            source = "history"
            if self.calibration > 1.15:
                revised_up = True
        else:
            base_rem = present_rem
            source = "throughput"

        lo, hi = E.conformal_interval(base_rem, self._dts, self._done_sizes)
        conf = self._confidence(frac, lo, hi, base_rem, source)
        note = ""
        if revised_up and source == "measured":
            note = "remaining work looks heavier than what's done so far"
        elif source == "measured" and self._sketch_note:
            note = self._sketch_note
        elif source == "history" and self.calibration_conf == "high":
            note = "adjusted using this job past runs"
        return EtaEstimate(done, total, frac, elapsed, base_rem, lo, hi,
                           conf, source, revised_up, note)

    def _confidence(self, frac, lo, hi, mid, source):
        rel = (hi - lo) / max(1e-9, mid)          # relative range width
        if source in ("measured", "history") and rel < 0.25:
            return "high"
        if frac < 0.05 or rel > 0.6:
            return "low"
        if rel < 0.35:
            return "high"
        return "medium"

    # ----- future-work sketch: caller measures sampled items, feeds back result -----
    def sample_plan_full(self, budget=0.02, min_items=50):
        """Sample indices across the FULL item set (measure mode, before the loop).
        Stratified by size.

        Sample-size discipline (honest survey statistics): a rare heavy tail cannot be
        estimated from a couple of draws. On LARGE jobs a small fraction suffices; on
        SMALL jobs we need a larger fraction. So the effective sample is
        max(min_items, budget*N), capped so we never sample the whole job. This is the
        accuracy/cost tradeoff, made explicit."""
        if not self.sizes or not self.total:
            return []
        N = self.total
        sz = [max(1e-9, self.sizes[j]) for j in range(N)]
        # want at least min_items, and at least budget*N.
        m = min(N, max(int(round(budget * N)), min(min_items, N)))
        distinct = len(set(sz))
        if distinct <= 1:
            # No size signal: use SYSTEMATIC sampling across item ORDER. For a
            # back-loaded/regime job this guarantees proportional coverage of every
            # part of the run (incl. the tail), which uniform random does not -- it
            # collapses the tail-count variance that otherwise wrecks the estimate.
            step = N / m
            picks = sorted({min(N - 1, int(round(k * step))) for k in range(m)})
            return picks
        # Otherwise stratify by size so heavy classes are represented.
        strata = E._strata_by_size(sz, E.N_STRATA)
        import random as _r
        rng = _r.Random(hash(self.workflow_key or "") & 0xFFFF)
        picks = []
        for st in strata:
            mh = max(1, min(len(st), max(1, int(round(m * len(st) / N)))))
            picks += rng.sample(st, mh)
        return sorted(picks)

    def apply_sample(self, measured):
        """measured: dict {item_index: measured_seconds} for sampled items. Store the
        per-index costs; estimate() uses the sampled items still AHEAD to project the
        remaining cost, so a heavy tail sampled up front stays represented and the
        estimate sharpens as the loop consumes items."""
        if not self.sizes or not measured or not self.total:
            return
        self._sample_costs = dict(measured)
