ASSET_CRITICALITY = {
    "Authentication Service": 1.0,
    "Payment Gateway": 1.0,
    "Customer Database": 1.0,
    "Internal Admin Panel": 0.8,
    "Internal API": 0.6,
    "Default": 0.5
}

# Service-to-Service Authentication
# CRITICAL FIX: Load from environment variable, fail fast if missing
import os

SERVICE_SECRET_KEY = os.getenv("SERVICE_SECRET_KEY")
if not SERVICE_SECRET_KEY:
    raise ValueError(
        "SERVICE_SECRET_KEY environment variable is required. "
        "Set it in docker-compose.yml or environment before starting the service."
    )

# Model & Prompt Versioning (for audit trail)
MODEL_VERSION = "phi3:mini"
PROMPT_VERSION = "1.1.0"  # Updated for Phi-3 Mini optimization
GUARDRAIL_VERSION = "1.0.0"

# AI Output Drift Detection Thresholds
DRIFT_THRESHOLDS = {
    "confidence_drop_percent": 5.0,  # 5% drop in confidence
    "remediation_steps_variance_percent": 30.0,  # ±30% variance
    "severity_distribution_shift_threshold": 0.1,  # If a severity appears less than this in baseline, it's a shift
    "risk_score_median_shift_points": 10,  # 10 point shift in median
    "min_samples_for_baseline": 10  # Minimum samples required to consider a baseline valid
}

# SLA Configuration
SLA_LATENCY_THRESHOLD_MS = 2000.0  # 2 seconds - threshold for load-aware degradation

# Model Promotion Configuration
PROMOTION_CONFIDENCE_THRESHOLD = 0.80  # 80% confidence required for auto-promotion (lowered from 0.85)
PROMOTION_SUCCESS_RATE_THRESHOLD = 0.95  # 95% success rate required when SLA is violated
PROMOTION_LATENCY_MULTIPLIER = 10.0  # Allow promotion if latency ≤ 10x SLA threshold
