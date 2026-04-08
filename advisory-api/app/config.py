import os

# ─── Asset criticality weights ──────────────────────────────
ASSET_CRITICALITY = {
    "Authentication Service": 1.0,
    "Payment Gateway": 1.0,
    "Customer Database": 1.0,
    "Internal Admin Panel": 0.8,
    "Internal API": 0.6,
    "Default": 0.5
}

# ─── Service-to-Service Authentication ──────────────────────
SERVICE_SECRET_KEY = os.getenv("SERVICE_SECRET_KEY")
if not SERVICE_SECRET_KEY:
    raise ValueError(
        "SERVICE_SECRET_KEY environment variable is required. "
        "Copy .env.example to .env and set all values before starting."
    )

# ─── Model & Prompt Versioning (audit trail) ────────────────
MODEL_VERSION = os.getenv("MODEL_VERSION", "phi3:mini")
PROMPT_VERSION = "1.1.0"
GUARDRAIL_VERSION = "1.0.0"

# ─── AI Output Drift Detection Thresholds ───────────────────
DRIFT_THRESHOLDS = {
    "confidence_drop_percent": 5.0,
    "remediation_steps_variance_percent": 30.0,
    "severity_distribution_shift_threshold": 0.1,
    "risk_score_median_shift_points": 10,
    "min_samples_for_baseline": 10
}

# ─── SLA Configuration ──────────────────────────────────────
SLA_LATENCY_THRESHOLD_MS = float(os.getenv("SLA_LATENCY_THRESHOLD_MS", "2000.0"))

# ─── Model Promotion Configuration ──────────────────────────
PROMOTION_CONFIDENCE_THRESHOLD = float(os.getenv("PROMOTION_CONFIDENCE_THRESHOLD", "0.80"))
PROMOTION_SUCCESS_RATE_THRESHOLD = float(os.getenv("PROMOTION_SUCCESS_RATE_THRESHOLD", "0.95"))
PROMOTION_LATENCY_MULTIPLIER = float(os.getenv("PROMOTION_LATENCY_MULTIPLIER", "10.0"))

# ─── Qdrant Configuration ───────────────────────────────────
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# ─── Ollama Configuration ───────────────────────────────────
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434/api/generate")

# ─── Demo Mode ──────────────────────────────────────────────
# When DEMO_MODE=true the API returns mock advisory responses
# so the live demo works without a running Ollama instance.
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

# ─── Rate Limiting ──────────────────────────────────────────
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
