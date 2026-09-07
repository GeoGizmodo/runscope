# Contributing to RunScope

Thanks for taking a look. RunScope is an early alpha and my first open-source project,
so feedback of any kind is genuinely welcome, from typo fixes to new ideas.

## Ways to help

- Try it on a real job and tell me where the ETA was good or bad (open an issue with
  the workload shape and what happened).
- Report bugs, especially anything where the estimate is misleading or the bar renders
  oddly on your terminal or OS.
- Suggest features or send a PR.

## Development setup

```bash
git clone https://github.com/GeoGizmodo/runscope.git
cd runscope
pip install -e .
python smoke.py            # quick sanity check
python examples/demo_shapes.py
```

No third-party dependencies for the core library. Please keep it that way unless a
dependency is clearly worth it.

## A note on the estimators

The math in `runscope/estimators.py` comes from a research program with preregistered
validation gates. If you change how an estimate is computed, please include a small
before/after accuracy comparison (see `examples/demo_shapes.py` for the pattern) so we
can be sure a change actually helps and does no harm on easy jobs.

## Pull requests

- Keep changes focused and small where possible.
- Run `python smoke.py` before submitting.
- Describe what you tested.

## Code of conduct

Be kind and constructive. This is a small, friendly project.
