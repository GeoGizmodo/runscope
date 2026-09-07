# Changelog

All notable changes to RunScope are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/).

## [0.1.8] - alpha

### Fixed
- PyPI "Source" / "Issues" / "Changelog" links now correctly point to
  github.com/GeoGizmodo/runscope (0.1.7 shipped with a placeholder URL by mistake).
  Removed the dead Documentation link.

## [0.1.7] - alpha

### Changed
- README science note reworded (removed jargon; clearer margin-of-error phrasing).

## [0.1.6] - alpha

### Changed
- Cleaner workload prompt: one choice per line, readable, and far fewer Star Wars
  flourishes. Removed the repeated quotes from event and summary lines (the `[Mode]`
  tag stays). When Jedi is active it no longer also prints the Master line.

## [0.1.5] - alpha

### Changed
- The workload question now asks **by default** (prompt=True) whenever a `measure_fn`
  is available and the terminal is interactive - and RunScope adapts to the answer
  (Jedi for back-loaded/uneven/slow-phase, Padawan for steady). Pass `prompt=False` to
  skip it. Scripts/CI/notebooks are never prompted or blocked.

## [0.1.4] - alpha

### Added
- **`prompt=True`**: an interactive "Use the Force?" workload question that offers Jedi
  when the job is back-loaded / uneven / has a slow phase (defaults to Jedi on Enter).
  Interactive terminals only; scripts/CI are never blocked.
- README: sample usage + terminal-style sample output; design-based sampling note with
  the author's adaptive-cluster-sampling paper citation (arXiv:1304.2460).
- A single, once-per-process link to the docs on the completion line.

### Changed
- Pro pricing set to **$4/month** (covers cloud costs). Padawan + Master free forever.

## [0.1.3] - alpha

### Added
- **Jedi opt-in.** The first time you use `measure=True`, RunScope asks once whether to
  enable Jedi (future-work sampling) and remembers the choice in `~/.runscope`.
  Non-interactive runs auto-opt-in during the free period so scripts/CI aren't blocked.
- Jedi is **free for everyone through Sep 30, 2026**, then part of RunScope Pro.
  Padawan (current-run) and Master (recurring-job history) remain free forever.

## [0.1.2] - alpha

### Fixed (important)
- **Single-line progress bar** that no longer stacks/leaves stale rows on any OS.
- **Measure mode now tracks the tail's position** (uses sampled items still ahead), so
  the estimate is accurate across the WHOLE run, not just early on.
- **Present/Padawan mode is recency-aware**: the ETA reacts to a regime change (heavy
  tail) instead of hanging at a stale tiny value.
- All three modes route distinctly and correctly (Padawan / Jedi / Master).
- Removed decorative emojis from all output; clean `[Mode]` tags with Star Wars quotes.

## [0.1.1] - alpha

### Added / Fixed
- **Future-work sketch (measure mode) is now functional.** `track(..., measure=True,
  measure_fn=cost_of)` measures a small stratified sample of upcoming items before the
  main loop and revises the ETA when the remaining work is heavier than the prefix
  suggests. Requires `measure_fn(item) -> seconds` (a cheap per-item cost probe).
- Measured cost is stored as a rate (seconds per size-unit) so the estimate stays
  correct as the loop progresses.
- Removed the unused optional `cloud=` parameter and `login` CLI stub (no cloud in the
  free client).

## [0.1.0] - alpha

First public alpha. The estimation engine is lifted unchanged from the ETA-Proto
research program and its preregistered validation gates.

### Added
- `runscope.track(iterable, key=, weight=, measure=)` — wrap any iterable for a live,
  calibrated ETA with an honest range.
- `runscope.trange(n)` — drop-in replacement for `tqdm.trange`.
- Three estimation layers, applied invisibly:
  - **Present**: size-weighted current-run ETA.
  - **Past**: per-workflow historical calibration (activates after 3+ runs).
  - **Future**: stratified sample of remaining work for heterogeneous jobs (`measure=True`).
- Terminal progress bar with confidence and plain-language notes (no methodology jargon).
- Local run history under `~/.runscope` (offline; no account required).
- `runscope run script.py` — auto-upgrades `tqdm` bars in a target script.
- `runscope history <key>` — inspect learned calibration for a workflow.
- Optional cloud sync (`[cloud]` extra) for cross-machine history (Pro, opt-in).

### Notes
- Core client has **no third-party dependencies**.
- Works on enumerable workloads (loops over files/records/tiles/simulations). It does
  not estimate arbitrary opaque single operations, and says so rather than guessing.
