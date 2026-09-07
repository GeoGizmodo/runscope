"""
runscope -- calibrated ETAs and completion intelligence for long-running jobs.

Quick start:
    import runscope
    for item in runscope.track(items, key="my_job"):
        process(item)

Drop-in for tqdm:
    from runscope import trange
    for i in trange(10000, key="my_job"):
        ...
"""
from .api import track, trange
from .tracker import Tracker, EtaEstimate

__version__ = "0.1.6"
__all__ = ["track", "trange", "Tracker", "EtaEstimate"]
