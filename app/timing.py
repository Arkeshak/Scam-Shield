import time
from contextlib import contextmanager


class Timings:
    def __init__(self):
        self.items = []
        self._start = time.perf_counter()

    @contextmanager
    def step(self, stage: str, model: str):
        t = time.perf_counter()
        try:
            yield
        finally:
            self.items.append({
                "stage": stage,
                "model": model,
                "ms": int((time.perf_counter() - t) * 1000)
            })

    def summary(self):
        return {
            "timings": self.items,
            "total_ms": int((time.perf_counter() - self._start) * 1000)
        }
