---
name: Bug report
about: Something broke, or the ETA was misleading
title: "[bug] "
labels: bug
---

## What happened

A clear description of the problem. If the ETA was wrong, tell me what it said vs what
actually happened.

## How to reproduce

```python
# a minimal snippet if you can
```

## Workload shape (helps a lot)

- Roughly how many items?
- Was the cost even, or heavy at the start / middle / end?
- Did you pass `weight=` or `measure_fn=`?

## Environment

- OS:
- Python version:
- runscope version (`python -c "import runscope; print(runscope.__version__)"`):
- Terminal (VS Code, iTerm, plain shell, notebook, CI):
