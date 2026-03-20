"""
Metrics Collection (Hooks for future Prometheus integration)
Tracks counters and latency percentiles.
"""
import time
from threading import Lock
from typing import Dict, List
from collections import deque

class Metrics:
    """Thread-safe metrics counter with latency tracking."""
    
    def __init__(self, max_latency_samples: int = 1000):
        self._lock = Lock()
        self._counters: Dict[str, int] = {
            "requests_total": 0,  # Total requests (alias for total_requests)
            "total_requests": 0,  # Keep for backward compatibility
            "success_count": 0,
            "failures_total": 0,  # Total failures (alias for failure_count)
            "failure_count": 0,  # Keep for backward compatibility
            "degraded_total": 0,  # Total degraded requests (alias for degraded_count)
            "degraded_count": 0,  # Keep for backward compatibility
            "fallback_count": 0,  # Model fallback events
        }
        self._latency_samples: deque = deque(maxlen=max_latency_samples)
    
    def increment(self, metric_name: str, value: int = 1):
        """Increment a metric counter."""
        with self._lock:
            if metric_name in self._counters:
                self._counters[metric_name] += value
            else:
                self._counters[metric_name] = value
            
            # Sync aliases
            if metric_name == "total_requests":
                self._counters["requests_total"] = self._counters["total_requests"]
            elif metric_name == "failure_count":
                self._counters["failures_total"] = self._counters["failure_count"]
            elif metric_name == "degraded_count":
                self._counters["degraded_total"] = self._counters["degraded_count"]
    
    def record_latency(self, latency_ms: float):
        """Record a latency sample."""
        with self._lock:
            self._latency_samples.append(latency_ms)
    
    def _calculate_percentile(self, samples: List[float], percentile: float) -> float:
        """Calculate percentile from sorted samples."""
        if not samples:
            return 0.0
        sorted_samples = sorted(samples)
        index = int(len(sorted_samples) * percentile / 100)
        return sorted_samples[min(index, len(sorted_samples) - 1)]
    
    def get_metrics(self) -> Dict:
        """Get current metric values with latency percentiles."""
        with self._lock:
            samples = list(self._latency_samples)
            metrics_dict = self._counters.copy()
            
            if samples:
                metrics_dict["p50_latency_ms"] = self._calculate_percentile(samples, 50)
                metrics_dict["p95_latency_ms"] = self._calculate_percentile(samples, 95)
                metrics_dict["p99_latency_ms"] = self._calculate_percentile(samples, 99)
                metrics_dict["min_latency_ms"] = min(samples)
                metrics_dict["max_latency_ms"] = max(samples)
                metrics_dict["avg_latency_ms"] = sum(samples) / len(samples)
            else:
                metrics_dict["p50_latency_ms"] = 0.0
                metrics_dict["p95_latency_ms"] = 0.0
                metrics_dict["p99_latency_ms"] = 0.0
                metrics_dict["min_latency_ms"] = 0.0
                metrics_dict["max_latency_ms"] = 0.0
                metrics_dict["avg_latency_ms"] = 0.0
            
            # Ensure aliases are present
            metrics_dict["requests_total"] = metrics_dict.get("total_requests", 0)
            metrics_dict["failures_total"] = metrics_dict.get("failure_count", 0)
            metrics_dict["degraded_total"] = metrics_dict.get("degraded_count", 0)
            
            metrics_dict["latency_sample_count"] = len(samples)
            
            return metrics_dict
    
    def reset(self):
        """Reset all metrics (for testing)."""
        with self._lock:
            for key in self._counters:
                self._counters[key] = 0
            self._latency_samples.clear()

# Global metrics instance
metrics = Metrics()

