"""Quick smoke test of the runscope client (no cloud, no TTY needed)."""
import time
import runscope
from runscope.tracker import Tracker
from runscope import estimators as E


def test_estimators():
    # sizew on a back-loaded set: prefix cheap, remainder heavy
    pdt = [0.01] * 10
    psz = [1.0] * 10
    rsz = [1.0] * 5 + [40.0] * 5
    rem = E.sizew_naive(pdt, psz, rsz)
    assert rem > 0
    # sketch recovers heavy remainder from a sample
    rem_dts = [0.01] * 50 + [0.4] * 50
    rem_sizes = [1.0] * 50 + [40.0] * 50
    import random
    est, cost = E.strat_sketch(rem_dts, rem_sizes, 4, random.Random(0))
    true = sum(rem_dts)
    assert abs(est - true) / true < 0.5, (est, true)
    print(f"  estimators OK (sketch est={est:.2f} vs true={true:.2f})")


def test_tracker_present():
    n = 100
    sizes = [1.0] * 50 + [10.0] * 50
    tr = Tracker(total=n, sizes=sizes, workflow_key="t")
    for i in range(30):
        tr.update(i)
    est = tr.estimate()
    assert est.eta_remaining > 0
    assert est.range_lo <= est.eta_remaining <= est.range_hi
    print(f"  tracker Present OK (eta={est.eta_remaining:.4f}s conf={est.confidence} "
          f"source={est.source})")


def test_track_loop():
    out = []
    for x in runscope.track(range(20), key="smoke_loop", label="smoke"):
        out.append(x)
        time.sleep(0.001)
    assert out == list(range(20))
    print("  track() loop OK")


def test_measure_mode():
    # super-linear heavy tail: sketch should revise ETA up vs pure size-weighting
    n = 100
    sizes = [1.0] * 80 + [40.0] * 20
    truth = {i: (0.002 if sizes[i] == 1 else 0.24) for i in range(n)}
    tr = Tracker(total=n, sizes=sizes, workflow_key="m")
    plan = tr.sample_plan_full(0.05)
    tr.apply_sample({j: truth[j] for j in plan})
    # complete 20% (all cheap) so size-weighting sees only the light prefix
    import time as _t
    for i in range(20):
        tr._dts.append(truth[i]); tr._last = tr._start + sum(tr._dts)
        tr._done_sizes.append(sizes[i])
    est = tr.estimate()
    assert est.source == "measured", est.source
    assert est.revised_up, "sketch should catch the super-linear heavy tail"
    print(f"  measure mode OK (source={est.source}, revised_up={est.revised_up})")


def test_history_dormant_then_active():
    from runscope import history as H
    key = "smoke_hist_" + str(time.time())
    cal, conf = H.calibration(key)
    assert cal == 1.0 and conf == "low", "should be dormant with no history"
    for _ in range(5):
        H.record(key, naive_eta_at_decision=100.0, actual_total=120.0)
    cal, conf = H.calibration(key)
    assert abs(cal - 1.2) < 0.05, cal
    print(f"  history OK (dormant->active, learned k_w={cal:.2f} conf={conf})")


if __name__ == "__main__":
    print("runscope smoke test")
    test_estimators()
    test_tracker_present()
    test_track_loop()
    test_measure_mode()
    test_history_dormant_then_active()
    print("ALL OK")
