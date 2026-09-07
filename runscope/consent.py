"""
runscope.consent -- one-time opt-in for Jedi (future-work sampling) mode.

Padawan (current-run) and Master (recurring-job history) are always free and need no
opt-in. Jedi actively MEASURES a small sample of your upcoming work, which costs a
little extra compute -- so the first time you use measure=True we ask once, remember
the choice in ~/.runscope/config.json, and never ask again.

Jedi is FREE for everyone through 2026-09-30 while we test. After that it becomes part
of RunScope Pro. Nothing about Padawan/Master ever changes.
"""
import datetime
import json
import os
import sys

from .config import HOME as _HOME

_CFG = os.path.join(_HOME, "config.json")

FREE_UNTIL = datetime.date(2026, 9, 30)


def _load():
    try:
        return json.load(open(_CFG))
    except Exception:
        return {}


def _save(cfg):
    os.makedirs(_HOME, exist_ok=True)
    try:
        json.dump(cfg, open(_CFG, "w"))
    except Exception:
        pass


def free_period_active():
    return datetime.date.today() <= FREE_UNTIL


def jedi_opted_in():
    return bool(_load().get("jedi_opt_in"))


def ensure_jedi_consent(stream=None):
    """Return True if Jedi may run. Asks once (interactively) if not yet decided.
    Non-interactive (no TTY): auto-opt-in during the free period, so scripted/CI runs
    are never blocked. Records the choice."""
    stream = stream or sys.stderr
    cfg = _load()
    if "jedi_opt_in" in cfg:
        return bool(cfg["jedi_opt_in"])

    interactive = False
    try:
        interactive = sys.stdin.isatty() and stream.isatty()
    except Exception:
        interactive = False

    until = FREE_UNTIL.strftime("%b %d, %Y")
    if not interactive:
        # can't prompt; opt in for the free testing period, note it, don't block
        cfg["jedi_opt_in"] = True
        cfg["jedi_opt_in_auto"] = True
        _save(cfg)
        stream.write(f"RunScope: Jedi (future-work sampling) enabled "
                     f"(free through {until}).\n")
        stream.flush()
        return True

    stream.write(
        "\nRunScope: 'measure' mode uses Jedi - it samples a little of your\n"
        "upcoming work to predict heavy/uneven jobs far more accurately.\n"
        "Padawan and Master modes stay free forever; Jedi is FREE for everyone\n"
        f"through {until} while we test, then part of RunScope Pro.\n"
        "Opt in to Jedi now? [Y/n] ")
    stream.flush()
    try:
        ans = input().strip().lower()
    except Exception:
        ans = "y"
    ok = ans in ("", "y", "yes")
    cfg["jedi_opt_in"] = ok
    _save(cfg)
    if ok:
        stream.write(f"Jedi enabled. Free through {until}. Thanks for testing!\n\n")
    else:
        stream.write("Staying on Padawan/Master. Run with measure=True anytime.\n\n")
    stream.flush()
    return ok


# Workload shapes where sampling the future (Jedi) materially beats a naive estimate,
# per the ETA-Proto research: cost is uneven and NOT visible from the early items.
_JEDI_WORTH = {
    "1": ("back-loaded (heavy work near the end)", True),
    "2": ("uneven / heterogeneous (some items much slower)", True),
    "3": ("has a slow phase partway (I/O, throttling, contention)", True),
    "4": ("steady / uniform (every item about the same)", False),
    "5": ("not sure", True),
}


def ask_workload(stream=None):
    """Ask the user what kind of workload this is, and decide whether Jedi (future
    sampling) is worth it. Returns True if Jedi should be used.

    Only asks on an interactive terminal. In non-interactive contexts (scripts, CI,
    notebooks with no TTY) it returns False silently -- never blocks, never hangs.
    """
    stream = stream or sys.stderr
    try:
        interactive = sys.stdin.isatty() and stream.isatty()
    except Exception:
        interactive = False
    if not interactive:
        return False

    until = FREE_UNTIL.strftime("%b %d, %Y")
    stream.write(
        "\nRunScope - what does this workload look like?\n"
        "  1) back-loaded  (heavy work near the end)\n"
        "  2) uneven       (some items much slower)\n"
        "  3) slow phase   (a slowdown partway through)\n"
        "  4) steady       (every item about the same)\n"
        f"  1-3 sample the future for a sharper ETA (free through {until}).\n"
        "  Choose [1-4, or Enter to let RunScope decide]: ")
    stream.flush()
    try:
        ans = input().strip()
    except Exception:
        return False
    if ans == "4":
        stream.write("Steady work - the current-run estimate is enough.\n\n")
        stream.flush()
        return False
    # default (Enter / 1,2,3) -> sample the future
    cfg = _load()
    cfg["jedi_opt_in"] = True
    _save(cfg)
    stream.write("Sampling the future for a sharper ETA...\n\n")
    stream.flush()
    return True
