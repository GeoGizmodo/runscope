"""
runscope public API.

    for x in runscope.track(items, key="my_job"):        # full power
        work(x)

    from runscope import trange                            # tqdm drop-in
    for i in trange(10000, key="my_job"):
        work(i)

Layers wire together automatically and invisibly:
  Present  always (size-weighted current-run ETA)
  Past     when this workflow has >= history.MIN_RUNS prior runs
  Future   when measure=True (sample a tiny % of remaining work up front)

The user never sees the methodology. `weight` supplies per-item observable sizes
(unlocks size-weighting + the future sketch); if omitted, sizes are inferred cheaply
from common item types, else treated as equal.
"""
import inspect
import os

from .tracker import Tracker
from .render import TerminalRenderer
from . import history as H
from . import estimators as E

DECISION_FRAC = 0.20      # elapsed fraction at which naive ETA is snapshotted
_DOCS_SHOWN = False       # show the docs link only once per process


def _clock(sec_from_now):
    from .render import _fmt_clock
    return _fmt_clock(sec_from_now)


def _dur(sec):
    from .render import _fmt_dur
    return _fmt_dur(sec)


def _infer_size(item):
    try:
        if isinstance(item, str) and os.path.exists(item):
            return float(os.path.getsize(item)) or 1.0
        if hasattr(item, "__len__"):
            return float(len(item)) or 1.0
        if hasattr(item, "nbytes"):
            return float(item.nbytes) or 1.0
    except Exception:
        pass
    return 1.0


def _sizes_for(seq, weight):
    try:
        if weight is not None:
            return [max(1e-9, float(weight(x))) for x in seq]
        return [_infer_size(x) for x in seq]
    except Exception:
        return None


def track(iterable, key=None, label=None, weight=None, measure=False,
          measure_fn=None, budget=0.05, prompt=True):
    """Wrap an iterable; yield its items while rendering a live, calibrated ETA.

    measure=True enables the future-work sketch (Jedi): before the main loop, a tiny
    representative sample of the REMAINING items is measured to estimate the true
    remaining cost. Needs measure_fn(item) -> seconds (a cheap per-item cost probe).

    prompt (default True) asks the user, before the run, what kind of workload this is
    and adapts: back-loaded / uneven / slow-phase -> Jedi (samples the future);
    steady -> Padawan. Only asks on an interactive terminal and only when a measure_fn
    is available; scripts/CI/notebooks skip the question silently. Pass prompt=False
    to never ask.
    """
    seq = list(iterable)
    total = len(seq)
    sizes = _sizes_for(seq, weight)

    # interactive workload question -> may enable Jedi (needs a way to measure items)
    if prompt and not measure and sizes and measure_fn is not None:
        from . import consent
        if consent.ask_workload():
            measure = True

    if key is None:
        frm = inspect.stack()[1]
        key = H.default_key(script=os.path.basename(frm.filename),
                            extra=str(frm.lineno), n=total)
    cal, cal_conf = H.calibration(key)
    label = label or (key.split("|")[0] if key else "run")

    tr = Tracker(total=total, sizes=sizes, workflow_key=key,
                 calibration=cal, calibration_conf=cal_conf)
    rend = TerminalRenderer(label=label)

    # Jedi (measure mode) opt-in consent (only when the prompt didn't already handle it)
    if measure and sizes and measure_fn is not None:
        from . import consent
        if not consent.ensure_jedi_consent():
            measure = False

    # Announce Master only when Jedi is NOT taking over (avoid double announcements).
    if abs(cal - 1.0) > 1e-6 and not measure:
        rend.emit(f"RunScope [Master]: learned from {H.n_runs(key)} past runs, "
                  f"adjusting by x{cal:.2f}.")

    # future-work sketch (Jedi): measure a small representative sample of remaining
    # items, feed true costs back to the tracker.
    if measure and sizes and measure_fn is not None:
        plan = tr.sample_plan_full(budget)
        measured = {}
        for j in plan:
            try:
                measured[j] = float(measure_fn(seq[j]))
            except Exception:
                pass
        if measured:
            tr.apply_sample(measured)
            tr._sketch_note = f"checked {len(measured)} of {total} upcoming items"
            rend.emit(f"RunScope [Jedi]: sampled {len(measured)} upcoming items "
                      f"to gauge the real workload ahead.")
    elif measure and measure_fn is None:
        tr._sketch_note = "measure mode needs measure_fn(item)"

    naive_at_decision = None
    _revised = False
    _prev_eta = None
    _pred_total = None        # total-time prediction captured at the decision point
    _pred_mode = "throughput"
    _last_mode = None         # highest-sophistication mode we actually operated in
    try:
        for i, item in enumerate(seq):
            yield item
            tr.update(i)
            est = tr.estimate()
            total_eta_now = tr.elapsed + est.eta_remaining
            if naive_at_decision is None and est.frac >= DECISION_FRAC:
                # snapshot pure size-weighted naive remaining for history logging
                naive_at_decision = tr.elapsed + E.sizew_naive(
                    tr._dts, tr._done_sizes, tr._remaining_sizes())
                # capture the prediction the tool actually SHOWED at this point,
                # in whatever mode is active, for honest post-run validation.
                _pred_total = total_eta_now
                _pred_mode = est.source
            # event: a material MID-RUN upward revision (running longer than it
            # first looked). Announce once, past the warm-up.
            if (_prev_eta is not None and est.frac > 0.1 and not _revised
                    and total_eta_now > _prev_eta * 1.30):
                _revised = True
                rend.emit(f"RunScope: this run is taking longer than it first "
                          f"looked - revised finish ~{_clock(est.eta_remaining)}.")
            _prev_eta = total_eta_now
            if est.source != "throughput":
                _last_mode = est.source     # remember the highest mode we operated in
            rend.draw(est)
        # truthful final summary: actual elapsed, and how the early prediction did
        actual = tr.elapsed
        final_mode = _last_mode or _pred_mode
        tag = {"throughput": "Padawan", "measured": "Jedi",
               "history": "Master"}.get(final_mode, "Padawan")
        dotc = "\u00b7" if rend._uni else "|"
        if _pred_total:
            err = abs(_pred_total - actual) / max(1e-9, actual) * 100
            summary = (f"done in {_dur(actual)} {dotc} {total} items {dotc} "
                       f"[{tag}] estimate was within {err:.0f}%")
        else:
            summary = f"done in {_dur(actual)} {dotc} {total} items {dotc} [{tag}]"
        # show the docs link once per process, keeps output uncluttered
        global _DOCS_SHOWN
        if not _DOCS_SHOWN:
            summary += "   pypi.org/project/runscope"
            _DOCS_SHOWN = True
        rend.close(summary)
    finally:
        # log this run for the Past layer (log always; calibrate later)
        if naive_at_decision:
            H.record(key, naive_at_decision, tr.elapsed,
                     meta={"n": total})


def trange(n, **kwargs):
    """tqdm-compatible drop-in: `for i in trange(n): ...`."""
    return track(range(n), **kwargs)
