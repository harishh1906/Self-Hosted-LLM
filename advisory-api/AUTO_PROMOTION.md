# Automated Model Promotion and Adaptive Serving

## Overview

The ModelOptimizationEngine automatically promotes recommended models when confidence ≥ 0.85 and the recommended model differs from the currently active model. This enables adaptive serving without manual intervention.

## Database Schema

### `ai_active_models` Table

**Key Fields:**
- `org_id`: Organization ID (multi-tenancy isolation)
- `policy_id`: Policy profile ID (NULL for default policy)
- `active_model`: Currently active LLM model name
- `last_promoted_at`: Timestamp when model was last promoted
- `promotion_reason`: Reason for promotion (e.g., "latency_optimization", "cost_optimization")
- `confidence`: Confidence score (0.0-1.0) for the promotion
- `correlation_id`: Correlation ID for promotion logging

**Unique Constraint:** `(org_id, policy_id)` - One active model per org+policy combination

## Auto-Promotion Logic

### Confidence Calculation

Confidence is calculated based on:
1. **Sample Size** (40% weight):
   - < 10 requests: 0.0 confidence
   - 10-49 requests: 0.5 confidence
   - 50-199 requests: 0.75 confidence
   - ≥ 200 requests: 0.9 confidence

2. **Signal Strength** (60% weight):
   - Budget utilization > 80%: 0.95 signal strength
   - Drift frequency > 5%: 0.9 signal strength
   - Latency > 2000ms: 0.85 signal strength
   - Cost high but latency acceptable: 0.8 signal strength
   - Balanced: 0.7 signal strength

**Final Confidence:** `(sample_confidence * 0.4) + (signal_strength * 0.6)`

### Promotion Conditions

Auto-promotion occurs when:
1. **Confidence ≥ 0.85** (85% threshold)
2. **Recommended model differs** from currently active model
3. **Analysis data available** (minimum 10 requests in last 30 days)

### Promotion Reasons

- `budget_optimization`: Budget utilization > 80%
- `accuracy_optimization`: Drift frequency > 5%
- `latency_optimization`: Latency > 2000ms
- `cost_optimization`: Cost high but latency acceptable
- `balanced_optimization`: Balanced recommendation

## API Endpoints

### 1. Get Active Models

**Endpoint:** `GET /api/v1/ai/governance/active-models`

**Query Parameters:**
- `policy_id` (optional): Policy ID to filter by specific policy

**Authentication:** Required (JWT or service-to-service)

**Example Request:**
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/ai/governance/active-models"
```

**Example Request (Specific Policy):**
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/ai/governance/active-models?policy_id=1"
```

**Example Response (Single Policy):**
```json
{
  "org_id": "org-financial-001",
  "policy_id": 1,
  "active_model": "mistral:7b-instruct",
  "promotion_reason": "latency_optimization",
  "confidence": 0.92,
  "last_promoted_at": "2026-01-15T10:30:00Z",
  "correlation_id": "abc-123-def-456"
}
```

**Example Response (Multiple Policies):**
```json
{
  "org_id": "org-financial-001",
  "active_models": [
    {
      "org_id": "org-financial-001",
      "policy_id": 1,
      "active_model": "mistral:7b-instruct",
      "promotion_reason": "latency_optimization",
      "confidence": 0.92,
      "last_promoted_at": "2026-01-15T10:30:00Z",
      "correlation_id": "abc-123-def-456"
    },
    {
      "org_id": "org-financial-001",
      "policy_id": null,
      "active_model": "mistral:7b-instruct",
      "promotion_reason": "cost_optimization",
      "confidence": 0.88,
      "last_promoted_at": "2026-01-15T09:15:00Z",
      "correlation_id": "xyz-789-ghi-012"
    }
  ]
}
```

## Promotion Flow

1. **Analysis Trigger:**
   - When `/api/v1/ai/governance/model-optimization-recommendations` is called
   - Analyzes last 30 days of `ai_cost_analytics` data

2. **Confidence Calculation:**
   - Calculates confidence based on sample size and signal strength
   - Includes promotion reason

3. **Auto-Promotion Check:**
   - If confidence ≥ 0.85 and model differs → auto-promote
   - Updates `ai_active_models` table
   - Logs promotion with correlation_id

4. **Logging:**
   - Structured log with:
     - `correlation_id`: Request correlation ID
     - `org_id`: Organization ID
     - `policy_id`: Policy profile ID
     - `active_model`: Promoted model
     - `promotion_reason`: Reason for promotion
     - `confidence`: Confidence score

## Integration

### Advisory Response Schema

**✅ Unchanged:** The advisory response schema remains unchanged. Model promotion is internal and transparent to API consumers.

### Model Selection

The active model can be used in:
- Advisory generation (future enhancement)
- Cost tracking
- Performance monitoring
- Model A/B testing

## Logging

### Promotion Log Example

```json
{
  "timestamp": "2026-01-15T10:30:00Z",
  "level": "INFO",
  "message": "Model promoted",
  "correlation_id": "abc-123-def-456",
  "org_id": "org-financial-001",
  "policy_id": 1,
  "active_model": "mistral:7b-instruct",
  "promotion_reason": "latency_optimization",
  "confidence": 0.92
}
```

## Safety Features

- **Confidence Threshold:** Only promotes with ≥ 85% confidence
- **Model Difference Check:** Only promotes if model actually differs
- **Minimum Sample Size:** Requires at least 10 requests for analysis
- **Non-Blocking:** Promotion failures don't block recommendations
- **Audit Trail:** All promotions logged with correlation_id and org_id

## Multi-Tenancy

All active models are scoped by `org_id`:
- Organizations can only see their own active models
- Queries automatically filter by authenticated organization
- No cross-tenant data leakage

## Files Modified/Created

1. `app/db/models.py` - Added `AIActiveModel` model
2. `app/optimization/engine.py` - Added:
   - `calculate_confidence()`: Confidence calculation
   - `get_promotion_reason()`: Promotion reason determination
   - `get_current_active_model()`: Get current active model
   - `promote_model()`: Promote model to active
   - `get_active_models()`: Get active models for org
   - Updated `update_optimization_profile()`: Auto-promotion logic
3. `app/main.py` - Added active-models endpoint

## Future Enhancements

- Integration with advisory generation to use active model
- Model rollback on performance degradation
- A/B testing framework
- Promotion approval workflow (optional manual approval)
- Model performance tracking post-promotion
- Cost savings calculation

