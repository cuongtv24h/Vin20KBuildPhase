import numpy as np


class LatencyTracker:
    def __init__(self):
        self.latencies_ms = []

    def record(self, latency_ms: float):
        self.latencies_ms.append(latency_ms)

    def calculate_metrics(self) -> dict[str, float]:
        if not self.latencies_ms:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "mean": 0.0}

        return {
            "p50": np.percentile(self.latencies_ms, 50),
            "p95": np.percentile(self.latencies_ms, 95),
            "p99": np.percentile(self.latencies_ms, 99),
            "mean": np.mean(self.latencies_ms)
        }
