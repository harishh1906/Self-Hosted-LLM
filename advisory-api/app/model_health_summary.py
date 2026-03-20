"""
Model Health Summary for Control Plane
Provides comprehensive model health metrics for explainable AI serving.
"""
import logging
from typing import List, Dict
from datetime import datetime
from app.model_health import model_health_tracker, SLA_LATENCY_THRESHOLD
from app.performance_intelligence import performance_intelligence

logger = logging.getLogger(__name__)

def get_model_health_summary() -> List[Dict]:
    """
    Get comprehensive real-time model health summary for control plane.
    
    Tracks per model:
    - average latency
    - SLA violations
    - fallback usage
    - drift adjustment rate
    - confidence trend
    
    Returns:
    - model_name: Model identifier
    - usage_count: Total number of requests
    - avg_latency_ms: Average request latency
    - fallback_count: Number of fallback events
    - drift_adjustments: Number of drift adjustments
    - drift_adjustment_rate: Rate of drift adjustments (0.0-1.0)
    - last_used_at: ISO timestamp of last usage
    - sla_violations: Number of SLA violations (latency > threshold)
    - confidence_trend: Confidence trend information
    
    Note: Does not expose advisory content - only metrics.
    """
    models_health = model_health_tracker.get_all_models_health()
    
    summary_list = []
    
    for health in models_health:
        model_name = health["model_name"]
        
        # Get confidence trend
        confidence_trend = performance_intelligence.get_confidence_trend(model_name)
        confidence_trend_data = None
        if confidence_trend:
            confidence_trend_data = {
                "recent_avg": confidence_trend["recent_avg"],
                "older_avg": confidence_trend["older_avg"],
                "drop_percent": confidence_trend["drop_percent"],
                "is_declining": confidence_trend["is_declining"],
                "sample_count": confidence_trend["sample_count"]
            }
        
        # Extract all metrics from health data
        usage_count = health.get("total_requests", 0)
        avg_latency_ms = health.get("avg_latency_ms", 0.0)
        fallback_count = health.get("fallback_count", 0)
        drift_adjustments = health.get("drift_adjustment_count", 0)
        drift_adjustment_rate = health.get("drift_adjustment_rate", 0.0)
        sla_violations = health.get("sla_violation_count", 0)
        last_used_at = health.get("last_used")
        
        summary_list.append({
            "model_name": model_name,
            "usage_count": usage_count,
            "avg_latency_ms": round(avg_latency_ms, 2),
            "fallback_count": fallback_count,
            "drift_adjustments": drift_adjustments,
            "drift_adjustment_rate": round(drift_adjustment_rate, 4),
            "last_used_at": last_used_at,
            "sla_violations": sla_violations,
            "confidence_trend": confidence_trend_data
        })
    
    return summary_list

