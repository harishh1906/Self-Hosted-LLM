import logging
import time
import uuid
import os
from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.schemas import FindingInput, PolicyProfileUpdate
from app.advisory_engine import generate_advisory
from app.db.database import Base, engine, get_db
from app.db import models  # REQUIRED: forces model registration
from app.db.crud import create_advisory, create_audit_log, create_or_update_policy_profile, get_policy_profile
from app.vector_store import init_collection
from app.auth.dependencies import get_current_user_or_service
from app.auth.jwt import create_access_token
from app.config import MODEL_VERSION, PROMPT_VERSION, GUARDRAIL_VERSION, DEMO_MODE, RATE_LIMIT_PER_MINUTE
from app.health import get_readiness_status
from app.metrics import metrics
from app.circuit_breaker import circuit_breaker
from app.drift.detector import detect_drift, update_baseline
from app.analytics.service import (
    record_analytics,
    get_policy_cost_summary,
    get_policy_latency_summary,
    get_policy_success_summary
)
from app.optimization.engine import get_optimization_recommendations, get_active_models
from app.model_manager import model_manager
from app.model_health import model_health_tracker
from app.config import SLA_LATENCY_THRESHOLD_MS
from app.performance_intelligence import get_optimization_insights
from app.policy_effectiveness import get_policy_effectiveness
from app.model_health_summary import get_model_health_summary

# Configure structured logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Create database tables on startup (must be after models are imported)
Base.metadata.create_all(bind=engine)

# ─── Rate Limiter ───────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ─── FastAPI App ────────────────────────────────────────────
app = FastAPI(
    title="VirtueThreatX Advisory API",
    version="0.3.0",
    description=(
        "Self-hosted on-prem AI advisory and risk assessment engine. "
        "Analyzes security findings using local LLMs (Phi-3 via Ollama) "
        "with full multi-tenancy, policy governance, and drift detection."
    ),
    contact={
        "name": "Harish",
        "url": "https://github.com/harishh1906/Self-Hosted-LLM"
    },
    license_info={"name": "MIT"},
    openapi_tags=[
        {"name": "Health", "description": "Health and readiness checks"},
        {"name": "Auth", "description": "Authentication"},
        {"name": "Advisory", "description": "Security finding analysis"},
        {"name": "Policy", "description": "AI policy profile management"},
        {"name": "Governance", "description": "Model governance and analytics"},
        {"name": "Internal", "description": "Internal metrics and control plane"}
    ]
)

# ─── Rate Limiting Middleware ────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─── CORS Middleware ─────────────────────────────────────────
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    """Initialize Qdrant collection and bootstrap knowledge base on startup."""
    init_collection()
    # Seed the RAG knowledge base (skips if already seeded or Qdrant unavailable)
    try:
        from app.bootstrap_knowledge import bootstrap
        bootstrap()
        logger.info("Knowledge base bootstrapped successfully")
    except Exception as e:
        logger.warning(f"Knowledge base bootstrap failed (non-blocking): {e}")
    
    if DEMO_MODE:
        logger.warning("🔶 DEMO_MODE is ACTIVE — mock advisory responses will be returned")

@app.get("/health", tags=["Health"])
def health_check():
    """Public health check endpoint."""
    return {
        "status": "ok",
        "version": "0.3.0",
        "demo_mode": DEMO_MODE,
        "model": MODEL_VERSION
    }

@app.get("/internal/health")
def internal_health_check():
    """
    Internal health and readiness endpoint.
    Returns detailed status of all dependencies and circuit breaker state.
    """
    health_status = get_readiness_status()
    circuit_state = circuit_breaker.get_state()
    
    return {
        **health_status,
        "circuit_breaker": circuit_state
    }

@app.get("/internal/metrics")
def get_metrics():
    """
    Internal metrics endpoint.
    Returns current metric counters including:
    - requests_total: Total number of requests
    - failures_total: Total number of failures
    - degraded_total: Total number of degraded requests
    - p95_latency: 95th percentile latency in milliseconds
    """
    metrics_dict = metrics.get_metrics()
    
    # Return required metrics in standardized format
    return {
        "requests_total": metrics_dict.get("requests_total", 0),
        "failures_total": metrics_dict.get("failures_total", 0),
        "degraded_total": metrics_dict.get("degraded_total", 0),
        "p95_latency": metrics_dict.get("p95_latency_ms", 0.0),
        # Include additional metrics for completeness
        "p50_latency_ms": metrics_dict.get("p50_latency_ms", 0.0),
        "p99_latency_ms": metrics_dict.get("p99_latency_ms", 0.0),
        "avg_latency_ms": metrics_dict.get("avg_latency_ms", 0.0),
        "fallback_count": metrics_dict.get("fallback_count", 0),
        "success_count": metrics_dict.get("success_count", 0)
    }

@app.get("/internal/model-health")
def get_model_health():
    """
    Get real-time health metrics per model from ai_cost_analytics.
    
    Returns per-model aggregated metrics:
    - model_name: Model identifier
    - usage_count: Total number of requests
    - avg_latency_ms: Average request latency
    - tokens_used_total: Total tokens used
    - fallback_count: Number of fallback events (from audit logs)
    - drift_adjustments: Number of drift adjustments (from audit logs)
    - sla_violations: Number of SLA violations (latency > 2000ms)
    - last_used_at: ISO timestamp of last usage
    """
    from app.db.database import SessionLocal
    from sqlalchemy import func, and_, cast
    from sqlalchemy.dialects.postgresql import JSONB
    from datetime import datetime, timedelta
    from app.db.models import AICostAnalytics, AuditLog
    
    db: Session = SessionLocal()
    try:
        
        # Get model metrics from ai_cost_analytics (fast aggregation)
        model_stats = db.query(
            AICostAnalytics.model_name,
            func.count(AICostAnalytics.id).label('usage_count'),
            func.avg(AICostAnalytics.latency_ms).label('avg_latency'),
            func.sum(AICostAnalytics.tokens_used).label('tokens_total'),
            func.max(AICostAnalytics.created_at).label('last_used')
        ).filter(
            AICostAnalytics.model_name.isnot(None)
        ).group_by(
            AICostAnalytics.model_name
        ).all()
        
        # Get fallback and drift counts from audit logs (with timeout protection)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        models_list = []
        for stat in model_stats:
            model_name = stat.model_name
            if not model_name:
                continue
                
            # Count fallbacks and drift adjustments from audit logs
            try:
                # Use PostgreSQL JSONB operators properly for nested access
                # payload->'model_selection'->>'used_fallback'
                jsonb_payload = cast(AuditLog.payload, JSONB)
                fallback_count = db.query(AuditLog).filter(
                    and_(
                        AuditLog.created_at >= thirty_days_ago,
                        jsonb_payload.has_key('model_selection'),
                        jsonb_payload['model_selection'].astext.cast(JSONB)['used_fallback'].astext == 'true',
                        jsonb_payload['actual_model_used'].astext == model_name
                    )
                ).count()
                
                drift_count = db.query(AuditLog).filter(
                    and_(
                        AuditLog.created_at >= thirty_days_ago,
                        jsonb_payload.has_key('drift_status'),
                        jsonb_payload['drift_status'].astext == 'DRIFT_DETECTED',
                        jsonb_payload['actual_model_used'].astext == model_name
                    )
                ).count()
            except Exception:
                # Graceful degradation if JSONB query fails
                fallback_count = 0
                drift_count = 0
            
            # Count SLA violations (latency > 2000ms)
            sla_violations = db.query(AICostAnalytics).filter(
                and_(
                    AICostAnalytics.model_name == model_name,
                    AICostAnalytics.latency_ms > 2000.0
                )
            ).count()
            
            models_list.append({
                "model_name": model_name,
                "usage_count": stat.usage_count,
                "avg_latency_ms": round(float(stat.avg_latency or 0), 2),
                "tokens_used_total": int(stat.tokens_total or 0),
                "fallback_count": fallback_count,
                "drift_adjustments": drift_count,
                "sla_violations": sla_violations,
                "last_used_at": stat.last_used.isoformat() if stat.last_used else None
            })
        
        return {"models": models_list}
    except Exception as e:
        logger.error(f"Error getting model health: {e}", exc_info=True)
        # Graceful degradation - return empty list
        return {"models": []}
    finally:
        db.close()

@app.get("/internal/optimization-insights")
def get_optimization_insights_endpoint():
    """
    Get optimization insights for production intelligence feedback loops.
    
    Returns:
    - top_performing_models: Models ranked by performance (latency, fallback rate)
    - fallback_usage_stats: Overall fallback statistics
    - drift_adjustment_trends: Drift detection trends over time
    - policy_profile_effectiveness: Policy configuration effectiveness metrics
    - model_selection_decision_chains: Model selection decision chain per request (last 100)
    
    Note: Does not affect advisory responses - internal intelligence only.
    """
    try:
        return get_optimization_insights()
    except Exception as e:
        logger.error(f"Error getting optimization insights: {e}", exc_info=True)
        # Graceful degradation - return empty structure
        return {
            "top_performing_models": [],
            "fallback_usage_stats": {
                "total_fallbacks": 0,
                "total_requests": 0,
                "overall_fallback_rate": 0.0,
                "models_with_fallbacks": []
            },
            "drift_adjustment_trends": {
                "total_drift_events": 0,
                "events_by_date": {},
                "avg_events_per_day": 0.0
            },
            "policy_profile_effectiveness": [],
            "model_selection_decision_chains": []
        }

@app.get("/internal/policy-effectiveness")
def get_policy_effectiveness_endpoint():
    """
    Get policy effectiveness metrics.
    
    Returns:
    - policy_id: Policy profile ID
    - avg_confidence: Average confidence score
    - avg_latency: Average request latency
    - drift_frequency: Frequency of drift detection (0.0-1.0)
    - tenant_rating_average: Average tenant rating (1.0-5.0)
    """
    return {
        "policies": get_policy_effectiveness()
    }

@app.get("/internal/control-plane/model-health-summary")
def get_model_health_summary_endpoint():
    """
    Get real-time model health summary for control plane.
    
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
    return {
        "models": get_model_health_summary()
    }

@app.get("/api/v1/ai/governance/policy-cost-summary")
def policy_cost_summary(
    identity: dict = Depends(get_current_user_or_service),
    endpoint: str = Query("analyze", description="Endpoint name"),
    month: int = Query(None, ge=1, le=12, description="Month number (1-12)"),
    year: int = Query(None, ge=2020, description="Year")
):
    """
    Get monthly cost summary grouped by policy configuration.
    
    Query Parameters:
    - endpoint: Endpoint name (default: "analyze")
    - month: Month number (1-12), defaults to current month
    - year: Year, defaults to current year
    
    Returns:
    - Monthly tokens used per policy configuration
    - Cost estimates per policy configuration
    """
    org_id = identity.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id required")
    
    summaries = get_policy_cost_summary(org_id, endpoint, month, year)
    
    return {
        "org_id": org_id,
        "endpoint": endpoint,
        "month": month,
        "year": year,
        "summaries": summaries,
        "total_cost_usd": sum(s["total_cost_usd"] for s in summaries),
        "total_tokens": sum(s["total_tokens"] for s in summaries),
        "total_requests": sum(s["request_count"] for s in summaries)
    }

@app.get("/api/v1/ai/governance/policy-latency-summary")
def policy_latency_summary(
    identity: dict = Depends(get_current_user_or_service),
    endpoint: str = Query("analyze", description="Endpoint name"),
    month: int = Query(None, ge=1, le=12, description="Month number (1-12)"),
    year: int = Query(None, ge=2020, description="Year")
):
    """
    Get latency statistics grouped by policy configuration.
    
    Query Parameters:
    - endpoint: Endpoint name (default: "analyze")
    - month: Month number (1-12), defaults to current month
    - year: Year, defaults to current year
    
    Returns:
    - Latency statistics per policy configuration
    """
    org_id = identity.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id required")
    
    summaries = get_policy_latency_summary(org_id, endpoint, month, year)
    
    return {
        "org_id": org_id,
        "endpoint": endpoint,
        "month": month,
        "year": year,
        "summaries": summaries
    }

@app.get("/api/v1/ai/governance/policy-success-summary")
def policy_success_summary(
    identity: dict = Depends(get_current_user_or_service),
    endpoint: str = Query("analyze", description="Endpoint name"),
    month: int = Query(None, ge=1, le=12, description="Month number (1-12)"),
    year: int = Query(None, ge=2020, description="Year")
):
    """
    Get success/failure statistics grouped by policy configuration.
    
    Query Parameters:
    - endpoint: Endpoint name (default: "analyze")
    - month: Month number (1-12), defaults to current month
    - year: Year, defaults to current year
    
    Returns:
    - Success and failure statistics per policy configuration
    """
    org_id = identity.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id required")
    
    summaries = get_policy_success_summary(org_id, endpoint, month, year)
    
    return {
        "org_id": org_id,
        "endpoint": endpoint,
        "month": month,
        "year": year,
        "summaries": summaries
    }

@app.get("/api/v1/ai/governance/model-optimization-recommendations")
def model_optimization_recommendations(
    identity: dict = Depends(get_current_user_or_service),
    policy_id: int = Query(None, description="Optional policy ID to filter by specific policy"),
    request: Request = None
):
    """
    Get AI model optimization recommendations per organization and policy profile.
    
    Analyzes last 30 days of usage data and recommends optimal models based on:
    - Cost optimization (if cost is high but latency acceptable)
    - Latency optimization (if latency is high)
    - Accuracy optimization (if drift is frequent)
    - Budget optimization (if budget utilization > 80%)
    
    Query Parameters:
    - policy_id: Optional policy ID to filter by specific policy
    
    Returns:
    - Recommended model per policy configuration
    - Average cost, latency, drift frequency, and budget utilization
    """
    org_id = identity.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id required")
    
    # Generate correlation ID for promotion logging
    correlation_id = request.headers.get("X-Request-ID") if request else None
    
    recommendations = get_optimization_recommendations(org_id, policy_id, correlation_id)
    
    # If single policy requested, return single recommendation object (matching example format)
    if policy_id is not None and len(recommendations) == 1:
        return recommendations[0]
    
    # Otherwise return list format
    return {
        "org_id": org_id,
        "recommendations": recommendations
    }

@app.get("/api/v1/ai/governance/active-models")
def active_models(
    identity: dict = Depends(get_current_user_or_service),
    policy_id: int = Query(None, description="Optional policy ID to filter by specific policy")
):
    """
    Get currently active models per organization and policy profile.
    
    Shows which models are currently in use after automatic promotion.
    
    Query Parameters:
    - policy_id: Optional policy ID to filter by specific policy
    
    Returns:
    - Active model per policy configuration
    - Promotion reason, confidence, and last promotion timestamp
    """
    org_id = identity.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id required")
    
    active_models_list = get_active_models(org_id, policy_id)
    
    # If single policy requested, return single active model object (matching example format)
    if policy_id is not None and len(active_models_list) == 1:
        return active_models_list[0]
    
    # Otherwise return list format
    return {
        "org_id": org_id,
        "active_models": active_models_list
    }

@app.post("/api/v1/ai/governance/model-hot-reload")
def model_hot_reload(
    identity: dict = Depends(get_current_user_or_service),
    request: Request = None,
    model_name: str = Query(..., description="Model name to set as default"),
    org_id: str = Query(None, description="Optional org_id for org-specific model")
):
    """
    Hot-reload model configuration without service restart.
    Updates are persisted to database for cluster-wide consistency.
    
    Query Parameters:
    - model_name: Model name to set
    - org_id: Optional organization ID for org-specific model
    
    Returns:
    - Updated model configuration
    """
    requester_org_id = identity.get("org_id")
    correlation_id = request.headers.get("X-Request-ID") if request else None
    updated_by = identity.get("user_id") or identity.get("service_name")
    
    if org_id:
        # Set org-specific model
        if requester_org_id and requester_org_id != org_id:
            raise HTTPException(
                status_code=403,
                detail="Cannot set model for other organizations"
            )
        model_manager.set_org_model(
            org_id,
            model_name,
            enabled=True,
            updated_by=updated_by,
            correlation_id=correlation_id
        )
        return {
            "status": "success",
            "message": f"Model updated for organization {org_id} (cluster-wide)",
            "org_id": org_id,
            "model_name": model_name,
            "correlation_id": correlation_id
        }
    else:
        # Set default model (requires admin privileges - can be enhanced)
        model_manager.set_default_model(
            model_name,
            updated_by=updated_by,
            correlation_id=correlation_id
        )
        return {
            "status": "success",
            "message": "Default model updated (cluster-wide)",
            "model_name": model_name,
            "correlation_id": correlation_id
        }

@app.get("/api/v1/ai/governance/model-config")
def get_model_config(
    identity: dict = Depends(get_current_user_or_service)
):
    """
    Get current model configuration.
    
    Returns:
    - Current model configuration including default and org-specific models
    """
    org_id = identity.get("org_id")
    configs = model_manager.get_all_configs()
    
    # Filter org-specific configs if user is not admin
    if org_id:
        org_config = model_manager.get_org_model(org_id)
        return {
            "default_model": configs["default_model"],
            "org_model": org_config,
            "org_id": org_id
        }
    else:
        return configs

@app.post("/login", tags=["Auth"])
def login(username: str, role: str = "security_analyst", org_id: str = "demo-org"):
    """
    Generate JWT token for testing/demo.
    In production, validate credentials against a user database.
    """
    token = create_access_token(data={"sub": username, "role": role, "org_id": org_id})
    return {"access_token": token, "token_type": "bearer"}


# ─── Policy Management Endpoints ─────────────────────────────

@app.get("/api/v1/ai/governance/policy/{org_id}", tags=["Policy"])
def get_policy(
    org_id: str,
    identity: dict = Depends(get_current_user_or_service),
    db: Session = Depends(get_db)
):
    """
    Get the AI policy profile for an organization.
    Controls risk_tolerance, verbosity, compliance_mode, and remediation_style.
    """
    requester_org = identity.get("org_id")
    if requester_org and requester_org != org_id:
        raise HTTPException(status_code=403, detail="Cannot access policy for another organization")
    
    policy = get_policy_profile(db, org_id)
    if not policy:
        return {
            "org_id": org_id,
            "risk_tolerance": "medium",
            "verbosity": "balanced",
            "compliance_mode": "none",
            "remediation_style": "practical",
            "source": "default"
        }
    return {
        "org_id": policy.org_id,
        "risk_tolerance": policy.risk_tolerance,
        "verbosity": policy.verbosity,
        "compliance_mode": policy.compliance_mode,
        "remediation_style": policy.remediation_style,
        "created_at": policy.created_at.isoformat() if policy.created_at else None,
        "updated_at": policy.updated_at.isoformat() if policy.updated_at else None,
        "source": "database"
    }


@app.post("/api/v1/ai/governance/policy", tags=["Policy"])
def create_policy(
    profile: "PolicyProfileUpdate",
    identity: dict = Depends(get_current_user_or_service),
    db: Session = Depends(get_db)
):
    """
    Create or update the AI policy profile for an organization.
    
    Controls how the LLM generates advisories:
    - **risk_tolerance**: low | medium | high
    - **verbosity**: concise | balanced | detailed
    - **compliance_mode**: none | soc2 | iso | hipaa
    - **remediation_style**: practical | strict | educational
    """
    org_id = profile.org_id or identity.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id is required")
    
    requester_org = identity.get("org_id")
    if requester_org and requester_org != org_id:
        raise HTTPException(status_code=403, detail="Cannot modify policy for another organization")
    
    updated = create_or_update_policy_profile(
        db=db,
        org_id=org_id,
        risk_tolerance=profile.risk_tolerance,
        verbosity=profile.verbosity,
        compliance_mode=profile.compliance_mode,
        remediation_style=profile.remediation_style
    )
    return {
        "status": "ok",
        "org_id": updated.org_id,
        "risk_tolerance": updated.risk_tolerance,
        "verbosity": updated.verbosity,
        "compliance_mode": updated.compliance_mode,
        "remediation_style": updated.remediation_style
    }


@app.delete("/api/v1/ai/governance/policy/{org_id}", tags=["Policy"])
def delete_policy(
    org_id: str,
    identity: dict = Depends(get_current_user_or_service),
    db: Session = Depends(get_db)
):
    """
    Reset the AI policy profile for an organization to system defaults.
    """
    from app.db.models import AIPolicyProfile
    requester_org = identity.get("org_id")
    if requester_org and requester_org != org_id:
        raise HTTPException(status_code=403, detail="Cannot delete policy for another organization")
    
    policy = get_policy_profile(db, org_id)
    if not policy:
        raise HTTPException(status_code=404, detail=f"No custom policy found for org_id: {org_id}")
    
    db.delete(policy)
    db.commit()
    from app.policy_loader import policy_cache
    policy_cache.invalidate(org_id)
    return {"status": "deleted", "org_id": org_id, "message": "Policy reset to system defaults"}


# ─── Demo / Showcase Endpoint ────────────────────────────────

@app.post("/demo/analyze", tags=["Advisory"])
@limiter.limit(f"{RATE_LIMIT_PER_MINUTE}/minute")
def demo_analyze(request: Request, finding: FindingInput, db: Session = Depends(get_db)):
    """
    **Demo endpoint** — returns an advisory response without auth.
    Uses the real LLM engine if DEMO_MODE=false, or a static mock if true.
    """
    # If in DEMO_MODE, return the high-quality pre-generated mock
    if DEMO_MODE:
        return {
            "finding": finding.title,
            "advisory": {
                "risk_summary": "A SQL Injection vulnerability was detected in the user authentication module. Attackers can manipulate database queries to bypass authentication completely.",
                "business_impact": "Successful exploitation could result in unauthorized access to all user accounts and complete data exfiltration. Estimated impact: HIGH.",
                "severity": "Critical",
                "remediation_steps": [
                    "Implement parameterized queries in the authentication logic",
                    "Conduct a security review of all database-facing code",
                    "Enable WAF rules for SQLi pattern detection"
                ],
                "confidence": 0.95
            },
            "risk_assessment": {
                "risk_score": 92,
                "risk_level": "Critical",
                "sla": "24 hours",
                "justification": "Critical severity on a crown-jewel asset (Auth) warrants immediate remediation."
            },
            "demo_mode": True,
            "model_used": MODEL_VERSION,
            "note": "Static demo response. Set DEMO_MODE=false for live generation."
        }
    
    # Run the REAL advisory engine!
    try:
        correlation_id = str(uuid.uuid4())
        result, rag_available, policy, token_usage, used_fallback, applied_policy_params, degradation_used, explainability_data = generate_advisory(
            finding=finding,
            org_id="demo-org",
            correlation_id=correlation_id
        )
        
        return {
            "finding": finding.title,
            "advisory": result["advisory"],
            "risk_assessment": result["risk_assessment"],
            "demo_mode": False,
            "model_used": explainability_data.get("actual_model_used", MODEL_VERSION),
            "rag_used": rag_available,
            "correlation_id": correlation_id,
            "note": "Generated by local LLM (Phi-3)."
        }
    except Exception as e:
        logger.error(f"Live demo generation failed (Correlation ID: {correlation_id}): {e}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Local LLM engine encountered an error: {str(e)}"
        )


@app.post("/analyze", tags=["Advisory"])
@limiter.limit(f"{RATE_LIMIT_PER_MINUTE}/minute")
def analyze_finding(
    finding: FindingInput,
    identity: dict = Depends(get_current_user_or_service),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Analyze a security finding and generate advisory.
    
    Supports both:
    - User JWT authentication (Authorization: Bearer <token>)
    - Service-to-service HMAC (X-Service-Name, X-Service-Signature, X-Timestamp)
    
    Multi-tenancy: org_id from finding or identity token.
    
    Correlation ID: Accepts X-Request-ID header, generates if missing.
    """
    # Correlation ID: Accept X-Request-ID header or generate
    if request:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    else:
        request_id = str(uuid.uuid4())
    
    start_time = time.time()
    
    # Extract context for logging
    org_id_for_log = finding.org_id or identity.get("org_id")
    service_name = identity.get("service_name") if identity.get("auth_type") == "service" else None
    user_id = identity.get("user_id") if identity.get("auth_type") == "user" else None
    
    logger.info(
        f"Request started",
        extra={
            "correlation_id": request_id,
            "org_id": org_id_for_log,
            "service_name": service_name,
            "user_id": user_id,
            "finding_title": finding.title[:100],
            "model_version": MODEL_VERSION,
            "active_model": finding.active_model,
            "rollback_flag": finding.rollback_flag
        }
    )
    
    try:
        # CRITICAL FIX: Enforce org_id consistency
        # If both finding.org_id and identity.org_id exist and differ → 400 error
        finding_org_id = finding.org_id
        identity_org_id = identity.get("org_id")
        
        if finding_org_id and identity_org_id and finding_org_id != identity_org_id:
            raise HTTPException(
                status_code=400,
                detail="org_id mismatch between finding and identity"
            )
        
        # Multi-tenancy: Extract org_id from finding or identity
        org_id = finding_org_id or identity_org_id
        
        # Enforce multi-tenancy isolation
        if not org_id:
            raise HTTPException(
                status_code=400,
                detail="org_id required for multi-tenant isolation"
            )
        
        # Get active model: check rollback_flag first, then prioritize request payload, then check database
        from app.ollama_client import MODEL_NAME, FALLBACK_MODEL
        
        # Runtime rollback: if rollback_flag is true, use default model
        if finding.rollback_flag:
            active_model = None  # Will use default MODEL_NAME
        else:
            active_model = finding.active_model
            if not active_model:
                # Get from active_models table if not in request
                from app.optimization.engine import get_current_active_model
                # Try to get policy-specific model first (will be set after policy is loaded)
                # For now, get default policy model
                active_model = get_current_active_model(org_id, None)
        
        # Final fallback to default model
        if not active_model:
            active_model = MODEL_NAME
        
        # Generate advisory with timing
        llm_start_time = time.time()
        result, rag_available, policy, token_usage, used_fallback, applied_policy_params, degradation_used, explainability_data = generate_advisory(
            finding,
            org_id=org_id,
            active_model=active_model,
            correlation_id=request_id
        )
        llm_latency_ms = (time.time() - llm_start_time) * 1000
        total_latency_ms = (time.time() - start_time) * 1000
        
        # Track fallback events
        if used_fallback:
            metrics.increment("fallback_count")
            logger.warning(
                f"Model failover occurred",
                extra={
                    "correlation_id": request_id,
                    "org_id": org_id,
                    "primary_model": active_model,
                    "fallback_model": FALLBACK_MODEL
                }
            )
        
        # Determine which model was actually used (fallback or primary)
        actual_model_used = FALLBACK_MODEL if used_fallback else active_model
        
        # Extract policy_id for logging and audit
        policy_id = policy.get("policy_id")
        
        # Extract token usage
        input_tokens = token_usage.get("prompt_eval_count")
        output_tokens = token_usage.get("eval_count")
        total_tokens = token_usage.get("total_tokens", 0) or (input_tokens or 0) + (output_tokens or 0)
        
        # AI Output Drift Detection: Check for drift (before audit log and model health tracking)
        drift_status, drift_reasons = detect_drift(
            endpoint="analyze",
            policy_id=policy_id,
            advisory_result=result,
            org_id=org_id,
            correlation_id=request_id
        )
        
        # Track model health metrics (after drift detection)
        drift_adjusted = drift_status == "DRIFT_DETECTED"
        model_health_tracker.record_request(
            model_name=actual_model_used,
            latency_ms=llm_latency_ms,
            used_fallback=used_fallback,
            drift_adjusted=drift_adjusted
        )
        
        # Log model selection decision for auditability
        from datetime import datetime
        model_selection_decision = {
            "selected_model": actual_model_used,
            "primary_model": active_model,
            "used_fallback": used_fallback,
            "fallback_model": FALLBACK_MODEL if used_fallback else None,
            "selection_timestamp": datetime.utcnow().isoformat()
        }
        
        # If active_model not in request and we have policy_id, try to get policy-specific model
        if not finding.active_model and policy_id is not None:
            from app.optimization.engine import get_current_active_model
            policy_active_model = get_current_active_model(org_id, policy_id)
            if policy_active_model:
                active_model = policy_active_model
        
        # If drift detected, lower advisory confidence and prepare fallback notice
        original_confidence = result["advisory"].confidence
        drift_fallback_notice = None
        
        if drift_status == "DRIFT_DETECTED":
            # Lower confidence by 10% (minimum 0.1)
            adjusted_confidence = max(0.1, original_confidence - 0.1)
            result["advisory"].confidence = round(adjusted_confidence, 2)
            
            # Prepare fallback notice for drift
            drift_fallback_notice = f"Drift detected: {', '.join(drift_reasons)}. Confidence adjusted from {original_confidence:.2f} to {adjusted_confidence:.2f}."
        
        # Merge self-healing fallback notice with drift fallback notice
        self_healing_notice = explainability_data.get("fallback_notice")
        fallback_notice = None
        if self_healing_notice and drift_fallback_notice:
            fallback_notice = f"{self_healing_notice} {drift_fallback_notice}"
        elif self_healing_notice:
            fallback_notice = self_healing_notice
        elif drift_fallback_notice:
            fallback_notice = drift_fallback_notice
            
            logger.warning(
                f"Drift detected - confidence lowered",
                extra={
                    "correlation_id": request_id,
                    "org_id": org_id,
                    "policy_id": policy_id,
                    "original_confidence": original_confidence,
                    "adjusted_confidence": adjusted_confidence,
                    "drift_reasons": drift_reasons
                }
            )
        
        # HIGH PRIORITY FIX: Database error handling with rollback
        try:
            # Save to database with org_id
            advisory_record = create_advisory(db, finding, result, org_id=org_id)
            
            # Audit log with full compliance trail (includes drift detection)
            user_id = identity.get("user_id") if identity.get("auth_type") == "user" else None
            service_name = identity.get("service_name") if identity.get("auth_type") == "service" else None
            
            # Extract metrics for drift detection
            advisory = result["advisory"]
            remediation_steps_count = len(advisory.remediation_steps) if advisory.remediation_steps else 0
            description_length = len(advisory.risk_summary or "") + len(advisory.business_impact or "")
            
            create_audit_log(
                db=db,
                action="analyze_finding",
                payload={
                    "finding_title": finding.title,
                    "finding_description": finding.description,
                    "scanner": finding.scanner,
                    "model": MODEL_VERSION,
                    "model_version": MODEL_VERSION,
                    "prompt_version": PROMPT_VERSION,
                    "guardrail_version": GUARDRAIL_VERSION,
                    "confidence": result["advisory"].confidence,
                    "risk_score": result["risk_assessment"]["risk_score"],
                    "risk_level": result["risk_assessment"]["risk_level"],
                    "remediation_steps_count": remediation_steps_count,
                    "description_length": description_length,
                    "severity": advisory.severity,
                    "advisory_id": advisory_record.id,
                    "auth_type": identity.get("auth_type"),
                    "rag_available": rag_available,
                    "llm_latency_ms": llm_latency_ms,
                    "total_latency_ms": total_latency_ms,
                    "correlation_id": request_id,
                    "policy_id": policy_id,
                    "policy_risk_tolerance": policy.get("risk_tolerance"),
                    "policy_verbosity": policy.get("verbosity"),
                    "policy_compliance_mode": policy.get("compliance_mode"),
                    "policy_remediation_style": policy.get("remediation_style"),
                    "drift_status": drift_status,
                    "drift_reasons": drift_reasons,
                    "active_model": active_model,
                    "fallback_notice": fallback_notice,
                    "response_time_ms": total_latency_ms,
                    "model_confidence": result["advisory"].confidence,
                    "used_fallback": used_fallback,
                    "model_selection_decision": model_selection_decision,
                    "applied_policy_params": applied_policy_params,
                    "degradation_used": degradation_used,
                    "decision_reason": explainability_data.get("decision_reason"),
                    "active_model": explainability_data.get("primary_model"),
                    "fallback_model": explainability_data.get("fallback_model"),
                    "actual_model_used": explainability_data.get("actual_model_used"),
                    "model_name_used": actual_model_used,  # For easy querying
                    "applied_policy_params": applied_policy_params,
                    "model_selection": {
                        "selected_model": explainability_data.get("actual_model_used"),
                        "primary_model": explainability_data.get("primary_model"),
                        "fallback_model": explainability_data.get("fallback_model"),
                        "used_fallback": used_fallback,
                        "force_model": finding.force_model,
                        "model_override": finding.model_override
                    }
                },
                user_id=user_id,
                service_name=service_name,
                org_id=org_id,
                policy_id=policy_id
            )
            
            # Metrics: Track successful analyses and latency
            metrics.increment("total_requests")
            metrics.increment("success_count")
            metrics.record_latency(total_latency_ms)
            
            if rag_available:
                # RAG was used successfully
                pass
            else:
                metrics.increment("degraded_count")
            
            # Circuit breaker: Record successful request
            circuit_breaker.record_request(success=True, failed=False)
            
            # Update baseline (async in production, but synchronous for now)
            try:
                update_baseline("analyze", policy_id, result, org_id)
            except Exception as e:
                logger.warning(
                    f"Baseline update failed (non-blocking): {e}",
                    extra={"correlation_id": request_id, "org_id": org_id, "policy_id": policy_id}
                )
            
            # Log drift detection result
            if drift_status == "DRIFT_DETECTED":
                logger.warning(
                    f"AI output drift detected",
                    extra={
                        "correlation_id": request_id,
                        "org_id": org_id,
                        "policy_id": policy_id,
                        "drift_status": drift_status,
                        "drift_reasons": drift_reasons
                    }
                )
            
            # Record analytics (non-blocking)
            try:
                record_analytics(
                    org_id=org_id,
                    endpoint="analyze",
                    policy_id=policy_id,
                    policy_risk_tolerance=policy.get("risk_tolerance"),
                    policy_verbosity=policy.get("verbosity"),
                    policy_compliance_mode=policy.get("compliance_mode"),
                    tokens_used=total_tokens,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=total_latency_ms,
                    llm_latency_ms=llm_latency_ms,
                    success="success",
                    correlation_id=request_id,
                    model_name=actual_model_used
                )
            except Exception as e:
                logger.warning(
                    f"Analytics recording failed (non-blocking): {e}",
                    extra={"correlation_id": request_id, "org_id": org_id}
                )
            
            # Structured logging: Success (with policy tracking and SLA health reporting)
            logger.info(
                f"Request completed successfully",
                extra={
                    "correlation_id": request_id,
                    "org_id": org_id,
                    "service_name": service_name,
                    "model_version": MODEL_VERSION,
                    "active_model": active_model,
                    "rag_available": rag_available,
                    "llm_latency_ms": llm_latency_ms,
                    "total_latency_ms": total_latency_ms,
                    "response_time_ms": total_latency_ms,  # SLA health reporting
                    "model_confidence": result["advisory"].confidence,  # SLA health reporting
                    "risk_score": result["risk_assessment"]["risk_score"],
                    "policy_id": policy_id,
                    "policy_risk_tolerance": policy.get("risk_tolerance"),
                    "policy_verbosity": policy.get("verbosity"),
                    "tokens_used": total_tokens,
                    "drift_status": drift_status,
                    "rollback_flag": finding.rollback_flag,
                    "used_fallback": used_fallback
                }
            )
            
            # Return the advisory result
            return {
                "finding": finding.title,
                "advisory": result["advisory"].model_dump(),
                "risk_assessment": result["risk_assessment"]
            }
        except SQLAlchemyError as e:
            # Database errors: rollback and return 503
            total_latency_ms = (time.time() - start_time) * 1000
            metrics.increment("total_requests")
            metrics.increment("failure_count")
            metrics.record_latency(total_latency_ms)
            circuit_breaker.record_request(success=False, failed=True)
            
            # Record analytics for failure
            try:
                record_analytics(
                    org_id=org_id_for_log or "unknown",
                    endpoint="analyze",
                    policy_id=policy_id if 'policy_id' in locals() else None,
                    policy_risk_tolerance=policy.get("risk_tolerance") if 'policy' in locals() else None,
                    policy_verbosity=policy.get("verbosity") if 'policy' in locals() else None,
                    policy_compliance_mode=policy.get("compliance_mode") if 'policy' in locals() else None,
                    tokens_used=total_tokens if 'total_tokens' in locals() else 0,
                    input_tokens=input_tokens if 'input_tokens' in locals() else None,
                    output_tokens=output_tokens if 'output_tokens' in locals() else None,
                    latency_ms=total_latency_ms,
                    llm_latency_ms=llm_latency_ms if 'llm_latency_ms' in locals() else None,
                    success="failure",
                    error_type="database_error",
                    correlation_id=request_id
                )
            except Exception:
                pass  # Don't fail on analytics errors
            
            db.rollback()
            logger.error(
                f"Database error",
                extra={
                    "correlation_id": request_id,
                    "org_id": org_id_for_log,
                    "total_latency_ms": total_latency_ms
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable"
            )
    except ValueError as e:
        # Validation errors (guardrails)
        total_latency_ms = (time.time() - start_time) * 1000
        metrics.increment("total_requests")
        metrics.increment("failure_count")
        metrics.record_latency(total_latency_ms)
        circuit_breaker.record_request(success=False, failed=True)
        
        # Record analytics for validation failure
        try:
            record_analytics(
                org_id=org_id_for_log or "unknown",
                endpoint="analyze",
                policy_id=policy_id if 'policy_id' in locals() else None,
                policy_risk_tolerance=policy.get("risk_tolerance") if 'policy' in locals() else None,
                policy_verbosity=policy.get("verbosity") if 'policy' in locals() else None,
                policy_compliance_mode=policy.get("compliance_mode") if 'policy' in locals() else None,
                tokens_used=total_tokens if 'total_tokens' in locals() else 0,
                input_tokens=input_tokens if 'input_tokens' in locals() else None,
                output_tokens=output_tokens if 'output_tokens' in locals() else None,
                latency_ms=total_latency_ms,
                llm_latency_ms=llm_latency_ms if 'llm_latency_ms' in locals() else None,
                success="failure",
                error_type="validation_error",
                correlation_id=request_id
            )
        except Exception:
            pass  # Don't fail on analytics errors
        
        logger.warning(
            f"Validation error",
            extra={
                "correlation_id": request_id,
                "org_id": org_id_for_log,
                "error": str(e),
                "total_latency_ms": total_latency_ms
            }
        )
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, etc.)
        total_latency_ms = (time.time() - start_time) * 1000
        metrics.increment("total_requests")
        metrics.increment("failure_count")
        metrics.record_latency(total_latency_ms)
        circuit_breaker.record_request(success=False, failed=True)
        
        logger.warning(
            f"HTTP exception",
            extra={
                "correlation_id": request_id,
                "org_id": org_id_for_log,
                "total_latency_ms": total_latency_ms
            }
        )
        raise
    except Exception as e:
        # CRITICAL FIX: Sanitize error handling - no internal exceptions exposed
        total_latency_ms = (time.time() - start_time) * 1000
        metrics.increment("total_requests")
        metrics.increment("failure_count")
        metrics.record_latency(total_latency_ms)
        circuit_breaker.record_request(success=False, failed=True)
        
        # Record analytics for error
        try:
            record_analytics(
                org_id=org_id_for_log or "unknown",
                endpoint="analyze",
                policy_id=policy_id if 'policy_id' in locals() else None,
                policy_risk_tolerance=policy.get("risk_tolerance") if 'policy' in locals() else None,
                policy_verbosity=policy.get("verbosity") if 'policy' in locals() else None,
                policy_compliance_mode=policy.get("compliance_mode") if 'policy' in locals() else None,
                tokens_used=total_tokens if 'total_tokens' in locals() else 0,
                input_tokens=input_tokens if 'input_tokens' in locals() else None,
                output_tokens=output_tokens if 'output_tokens' in locals() else None,
                latency_ms=total_latency_ms,
                llm_latency_ms=llm_latency_ms if 'llm_latency_ms' in locals() else None,
                success="error",
                error_type="internal_error",
                correlation_id=request_id
            )
        except Exception:
            pass  # Don't fail on analytics errors
        
        logger.error(
            f"Internal error",
            extra={
                "correlation_id": request_id,
                "org_id": org_id_for_log,
                "service_name": service_name,
                "model_version": MODEL_VERSION,
                "total_latency_ms": total_latency_ms
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error. Request ID: {request_id}"
        )
