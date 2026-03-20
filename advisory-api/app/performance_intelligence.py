"""
Performance Intelligence and Feedback Loops
Continuously evaluates model performance and provides optimization insights.
"""
import logging
import statistics
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, cast, Integer
from sqlalchemy.dialects.postgresql import JSONB
from app.db.models import AICostAnalytics, AuditLog, AIOutputBaseline
from app.db.database import SessionLocal
from app.model_health import model_health_tracker

logger = logging.getLogger(__name__)

# Self-healing thresholds
CONFIDENCE_DROP_THRESHOLD = 0.1  # 10% drop triggers self-healing
CONFIDENCE_DROP_WINDOW = 10  # Check last 10 requests
SEVERITY_SENSITIVITY_REDUCTION = 0.1  # Reduce severity sensitivity by 10%

class PerformanceIntelligence:
    """Tracks model performance trends and provides optimization insights."""
    
    def __init__(self):
        self._confidence_history: Dict[str, List[float]] = {}  # model_name -> [confidence values]
        self._max_history = 100  # Keep last 100 confidence values per model
    
    def record_confidence(self, model_name: str, confidence: float):
        """Record confidence value for trend analysis."""
        if model_name not in self._confidence_history:
            self._confidence_history[model_name] = []
        
        history = self._confidence_history[model_name]
        history.append(confidence)
        
        # Keep only recent history
        if len(history) > self._max_history:
            history.pop(0)
    
    def get_confidence_trend(self, model_name: str) -> Optional[Dict]:
        """Get confidence trend for a model."""
        if model_name not in self._confidence_history:
            return None
        
        history = self._confidence_history[model_name]
        if len(history) < 5:
            return None
        
        recent = history[-CONFIDENCE_DROP_WINDOW:]
        older = history[-CONFIDENCE_DROP_WINDOW*2:-CONFIDENCE_DROP_WINDOW] if len(history) >= CONFIDENCE_DROP_WINDOW*2 else history[:-CONFIDENCE_DROP_WINDOW]
        
        if not older:
            return None
        
        recent_avg = statistics.mean(recent)
        older_avg = statistics.mean(older)
        
        drop_percent = ((older_avg - recent_avg) / older_avg * 100) if older_avg > 0 else 0
        
        return {
            "recent_avg": round(recent_avg, 3),
            "older_avg": round(older_avg, 3),
            "drop_percent": round(drop_percent, 2),
            "is_declining": drop_percent > (CONFIDENCE_DROP_THRESHOLD * 100),
            "sample_count": len(history)
        }
    
    def should_trigger_self_healing(self, model_name: str) -> bool:
        """Check if self-healing should be triggered for a model."""
        trend = self.get_confidence_trend(model_name)
        if not trend:
            return False
        
        return trend["is_declining"] and trend["drop_percent"] > (CONFIDENCE_DROP_THRESHOLD * 100)

# Global performance intelligence instance
performance_intelligence = PerformanceIntelligence()

def get_optimization_insights() -> Dict:
    """
    Get comprehensive optimization insights including:
    - top_performing_models (from ai_cost_analytics - ranked by latency & success rate)
    - fallback_usage_stats (count + rate)
    - drift_adjustment_trends (30-day grouped counts)
    - policy_profile_effectiveness (avg confidence + latency per policy_id)
    """
    db: Session = SessionLocal()
    try:
        from datetime import timedelta
        # 1. Top performing models (from ai_cost_analytics - ranked by lowest latency & highest success rate)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        model_performance = db.query(
            AICostAnalytics.model_name,
            func.avg(AICostAnalytics.latency_ms).label('avg_latency'),
            func.count(AICostAnalytics.id).label('request_count'),
            func.avg(cast(AICostAnalytics.success == 'success', Integer)).label('success_rate')
        ).filter(
            and_(
                AICostAnalytics.created_at >= thirty_days_ago,
                AICostAnalytics.model_name.isnot(None)
            )
        ).group_by(
            AICostAnalytics.model_name
        ).having(
            func.count(AICostAnalytics.id) >= 10  # Minimum 10 requests
        ).all()
        
        top_performing_models = []
        for perf in model_performance:
            # Performance score: lower latency + higher success rate = better
            latency_score = max(0.0, 1.0 / (1.0 + float(perf.avg_latency or 0) / 1000.0))
            success_score = float(perf.success_rate or 0)
            performance_score = (latency_score * 0.6) + (success_score * 0.4)  # Weighted combination
            
            top_performing_models.append({
                "model_name": perf.model_name,
                "avg_latency_ms": round(float(perf.avg_latency or 0), 2),
                "success_rate": round(success_score, 4),
                "total_requests": perf.request_count,
                "performance_score": round(performance_score, 4),
                "rank": 0
            })
        
        # Sort by performance score (descending)
        top_performing_models.sort(key=lambda x: x["performance_score"], reverse=True)
        for idx, model in enumerate(top_performing_models[:10], start=1):
            model["rank"] = idx
        top_performing_models = top_performing_models[:10]
        
        # 2. Fallback usage stats (from audit logs)
        try:
            # Use PostgreSQL JSONB operators: -> (JSONB) and ->> (text)
            # Proper nested access: payload->'model_selection'->>'used_fallback'
            jsonb_payload = cast(AuditLog.payload, JSONB)
            fallback_logs = db.query(AuditLog).filter(
                and_(
                    AuditLog.created_at >= thirty_days_ago,
                    jsonb_payload.has_key('model_selection'),
                    jsonb_payload['model_selection'].astext.cast(JSONB)['used_fallback'].astext == 'true'
                )
            ).count()
            
            total_requests = db.query(AuditLog).filter(
                AuditLog.created_at >= thirty_days_ago,
                AuditLog.action == 'analyze_finding'
            ).count()
            
            fallback_rate_overall = (fallback_logs / total_requests) if total_requests > 0 else 0.0
            
            # Models with fallbacks
            fallback_by_model = {}
            jsonb_payload = cast(AuditLog.payload, JSONB)
            fallback_audit_logs = db.query(AuditLog).filter(
                and_(
                    AuditLog.created_at >= thirty_days_ago,
                    jsonb_payload.has_key('model_selection'),
                    jsonb_payload['model_selection'].astext.cast(JSONB)['used_fallback'].astext == 'true'
                )
            ).all()
            
            for log in fallback_audit_logs:
                model_name = log.payload.get('actual_model_used') or 'unknown'
                fallback_by_model[model_name] = fallback_by_model.get(model_name, 0) + 1
            
            models_with_fallbacks = [
                {
                    "model_name": model_name,
                    "fallback_count": count
                }
                for model_name, count in fallback_by_model.items()
            ]
        except Exception as e:
            logger.warning(f"Error calculating fallback stats: {e}")
            fallback_logs = 0
            total_requests = 0
            fallback_rate_overall = 0.0
            models_with_fallbacks = []
        
        fallback_usage_stats = {
            "total_fallbacks": fallback_logs,
            "total_requests": total_requests,
            "overall_fallback_rate": round(fallback_rate_overall, 4),
            "models_with_fallbacks": models_with_fallbacks
        }
        
        # 3. Drift adjustment trends (from audit logs - with error handling)
        try:
            drift_logs = db.query(AuditLog).filter(
                and_(
                    AuditLog.created_at >= thirty_days_ago,
                    cast(AuditLog.payload, JSONB).has_key('drift_status'),
                    (cast(AuditLog.payload, JSONB)['drift_status'].astext) == 'DRIFT_DETECTED'
                )
            ).all()
        except Exception as e:
            logger.warning(f"Error querying drift logs: {e}")
            drift_logs = []
        
        # Group by date
        drift_by_date: Dict[str, int] = {}
        for log in drift_logs:
            date_str = log.created_at.date().isoformat()
            drift_by_date[date_str] = drift_by_date.get(date_str, 0) + 1
        
        drift_adjustment_trends = {
            "total_drift_events": len(drift_logs),
            "events_by_date": drift_by_date,
            "avg_events_per_day": round(len(drift_logs) / 30.0, 2) if drift_logs else 0.0
        }
        
        # 4. Policy profile effectiveness (avg confidence + latency per policy_id from analytics + audit logs)
        try:
            # Get policy stats from analytics
            policy_stats = db.query(
                AICostAnalytics.policy_id,
                func.avg(AICostAnalytics.latency_ms).label('avg_latency'),
                func.count(AICostAnalytics.id).label('request_count')
            ).filter(
                AICostAnalytics.created_at >= thirty_days_ago,
                AICostAnalytics.policy_id.isnot(None)
            ).group_by(
                AICostAnalytics.policy_id
            ).all()
            
            # Get average confidence from audit logs
            policy_profile_effectiveness = []
            for stat in policy_stats:
                # Get confidence from audit logs for this policy
                try:
                    confidence_logs = db.query(AuditLog).filter(
                        and_(
                            AuditLog.created_at >= thirty_days_ago,
                            (cast(AuditLog.payload, JSONB)['policy_id'].astext) == str(stat.policy_id),
                            cast(AuditLog.payload, JSONB).has_key('model_confidence')
                        )
                    ).all()
                    
                    confidences = []
                    for log in confidence_logs:
                        conf = log.payload.get('model_confidence')
                        if conf is not None:
                            try:
                                confidences.append(float(conf))
                            except (ValueError, TypeError):
                                pass
                    
                    avg_confidence = sum(confidences) / len(confidences) if confidences else None
                except Exception:
                    avg_confidence = None
                
                policy_profile_effectiveness.append({
                    "policy_id": stat.policy_id,
                    "avg_latency_ms": round(float(stat.avg_latency or 0), 2),
                    "request_count": stat.request_count,
                    "avg_confidence": round(avg_confidence, 3) if avg_confidence else None
                })
            
            # Sort by avg_confidence (descending), then by latency (ascending)
            policy_profile_effectiveness.sort(
                key=lambda x: (x["avg_confidence"] or 0, -x["avg_latency_ms"]),
                reverse=True
            )
        except Exception as e:
            logger.warning(f"Error calculating policy effectiveness: {e}")
            policy_profile_effectiveness = []
        
        # 5. Model selection decision chain per request (from audit logs - with error handling)
        try:
            recent_requests = db.query(AuditLog).filter(
                and_(
                    AuditLog.created_at >= thirty_days_ago,
                    cast(AuditLog.payload, JSONB).has_key('model_selection')
                )
            ).order_by(AuditLog.created_at.desc()).limit(100).all()
        except Exception as e:
            logger.warning(f"Error querying model selection chains: {e}")
            recent_requests = []
        
        model_selection_chains = []
        for log in recent_requests:
            model_selection = log.payload.get('model_selection', {})
            decision_reason = log.payload.get('decision_reason')
            applied_policy_params = log.payload.get('applied_policy_params', {})
            
            # Build comprehensive decision chain
            chain = {
                "correlation_id": log.correlation_id,
                "org_id": log.org_id,
                "policy_id": log.payload.get('policy_id'),
                "timestamp": log.created_at.isoformat(),
                "selected_model": model_selection.get("selected_model"),
                "primary_model": model_selection.get("primary_model"),
                "fallback_model": model_selection.get("fallback_model"),
                "actual_model_used": log.payload.get('actual_model_used') or model_selection.get("selected_model"),
                "used_fallback": model_selection.get("used_fallback", False),
                "force_model": model_selection.get("force_model"),
                "model_override": model_selection.get("model_override"),
                "decision_reason": decision_reason,
                "applied_policy_params": applied_policy_params,
                "response_time_ms": log.payload.get('response_time_ms'),
                "model_confidence": log.payload.get('model_confidence')
            }
            model_selection_chains.append(chain)
        
        return {
            "top_performing_models": top_performing_models,
            "fallback_usage_stats": fallback_usage_stats,
            "drift_adjustment_trends": drift_adjustment_trends,
            "policy_profile_effectiveness": policy_profile_effectiveness,
            "model_selection_decision_chains": model_selection_chains
        }
    except Exception as e:
        logger.error(f"Failed to get optimization insights: {e}", exc_info=True)
        return {
            "top_performing_models": [],
            "fallback_usage_stats": {"total_fallbacks": 0, "total_requests": 0, "overall_fallback_rate": 0.0, "models_with_fallbacks": []},
            "drift_adjustment_trends": {"total_drift_events": 0, "events_by_date": {}, "avg_events_per_day": 0.0},
            "policy_profile_effectiveness": [],
            "model_selection_decision_chains": []
        }
    finally:
        db.close()

