"""
runscope CLI.

  runscope run script.py [args...]   run a script; auto-instrument its loops/tqdm
  runscope history [key]             show learned calibration for your workflows

`run` installs a tqdm shim so existing `tqdm`/`trange` calls in the target script are
transparently upgraded to RunScope bars (removing the duplicate). Plain loops can be
instrumented by importing runscope.track directly.
"""
import runpy
import sys


def _install_tqdm_shim():
    """Monkeypatch tqdm so existing progress bars in the target script are replaced
    by RunScope. Best-effort: only affects tqdm-style bars, never crashes the run."""
    try:
        import tqdm as _tqdm
        from .api import track

        def _shim(iterable=None, *a, **k):
            if iterable is None:
                return _tqdm.std.tqdm(*a, **k)  # non-iterable usage: leave as-is
            key = k.get("desc") or None
            return track(iterable, key=key, label=k.get("desc"))
        _tqdm.tqdm = _shim
        _tqdm.trange = lambda n, *a, **k: _shim(range(n), *a, **k)
    except Exception:
        pass  # tqdm not installed / different API -> no-op


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd == "run":
        if len(argv) < 2:
            print("usage: runscope run script.py [args...]")
            return 2
        _install_tqdm_shim()
        sys.argv = argv[1:]
        runpy.run_path(argv[1], run_name="__main__")
        return 0
    if cmd == "history":
        from . import history as H
        key = argv[1] if len(argv) > 1 else None
        if not key:
            print("usage: runscope history <workflow_key>")
            return 2
        k, conf = H.calibration(key)
        data = H.load(key)
        print(f"workflow: {key}")
        print(f"  runs recorded: {len(data['runs'])}")
        print(f"  calibration:   x{k:.3f}  (confidence: {conf})")
        return 0
    print(f"unknown command: {cmd}")
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
