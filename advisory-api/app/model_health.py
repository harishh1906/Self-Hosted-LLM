"""
Model Health Tracking
Tracks real-time health metrics per model for production monitoring.
"""
import logging
import time
import statistics
from threading import Lock
from typing import Dict, Optional, List
from collections import deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# SLA threshold for latency (milliseconds)
SLA_LATENCY_THRESHOLD = 2000.0  # 2 seconds

class ModelHealthTracker:
    """Thread-safe model health tracker."""
    
    def __init__(self, max_samples: int = 1000):
        self._lock = Lock()
        self._max_samples = max_samples
        
        # Per-model tracking
        # Structure: model_name -> {
        #   "latency_samples": deque,
        #   "fallback_count": int,
        #   "drift_adjustment_count": int,
        #   "sla_violation_count": int,
        #   "total_requests": int,
        #   "last_used": datetime
        # }
        self._model_metrics: Dict[str, Dict] = {}
    
    def record_request(
        self,
        model_name: str,
        latency_ms: float,
        used_fallback: bool = False,
        drift_adjusted: bool = False
    ):
        """Record a request for a model."""
        with self._lock:
            if model_name not in self._model_metrics:
                self._model_metrics[model_name] = {
                    "latency_samples": deque(maxlen=self._max_samples),
                    "fallback_count": 0,
                    "drift_adjustment_count": 0,
                    "sla_violation_count": 0,
                    "total_requests": 0,
                    "last_used": datetime.utcnow()
                }
            
            metrics = self._model_metrics[model_name]
            metrics["latency_samples"].append(latency_ms)
            metrics["total_requests"] += 1
            metrics["last_used"] = datetime.utcnow()
            
            if used_fallback:
                metrics["fallback_count"] += 1
            
            if drift_adjusted:
                metrics["drift_adjustment_count"] += 1
            
            # Track SLA violations
            if latency_ms > SLA_LATENCY_THRESHOLD:
                metrics["sla_violation_count"] += 1
    
    def get_model_health(self, model_name: str) -> Optional[Dict]:
        """Get health metrics for a specific model."""
        with self._lock:
            if model_name not in self._model_metrics:
                return None
            
            metrics = self._model_metrics[model_name]
            latency_samples = list(metrics["latency_samples"])
            
            avg_latency = statistics.mean(latency_samples) if latency_samples else 0.0
            
            total_requests = metrics["total_requests"]
            fallback_rate = (metrics["fallback_count"] / total_requests) if total_requests > 0 else 0.0
            drift_adjustment_rate = (metrics["drift_adjustment_count"] / total_requests) if total_requests > 0 else 0.0
            
            # Check if model is "loaded" (has been used recently)
            last_used = metrics["last_used"]
            is_loaded = (datetime.utcnow() - last_used).total_seconds() < 3600  # Used in last hour
            
            return {
                "model_name": model_name,
                "is_loaded": is_loaded,
                "avg_latency_ms": round(avg_latency, 2),
                "fallback_count": metrics["fallback_count"],
                "fallback_rate": round(fallback_rate, 4),
                "drift_adjustment_rate": round(drift_adjustment_rate, 4),
                "drift_adjustment_count": metrics.get("drift_adjustment_count", 0),
                "sla_violation_count": metrics.get("sla_violation_count", 0),
                "total_requests": total_requests,
                "last_used": last_used.isoformat() if last_used else None
            }
    
    def get_all_models_health(self) -> List[Dict]:
        """Get health metrics for all tracked models."""
        with self._lock:
            health_list = []
            for model_name in self._model_metrics.keys():
                health = self.get_model_health(model_name)
                if health:
                    health_list.append(health)
            return health_list
    
    def is_model_healthy(self, model_name: str) -> bool:
        """Check if model meets SLA (latency < threshold)."""
        health = self.get_model_health(model_name)
        if not health:
            return True  # Unknown models considered healthy
        
        return health["avg_latency_ms"] < SLA_LATENCY_THRESHOLD

# Global model health tracker instance
model_health_tracker = ModelHealthTracker()

