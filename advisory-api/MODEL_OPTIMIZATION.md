# AI Model Portfolio Optimization

## Overview

The ModelOptimizationEngine automatically analyzes AI usage patterns and recommends optimal LLM models per organization and policy profile based on cost, latency, drift frequency, and budget utilization.

## Database Schema

### `ai_model_optimization_profiles` Table

**Key Fields:**
- `org_id`: Organization ID (multi-tenancy isolation)
- `policy_id`: Policy profile ID (NULL for default policy)
- `recommended_model`: Recommended LLM model name
- `avg_cost_per_request`: Average cost per request in USD
- `avg_latency_ms`: Average latency in milliseconds
- `drift_frequency`: Frequency of drift detection (0.0-1.0)
- `budget_utilization_percent`: Budget utilization percentage (0.0-100.0)
- `updated_at`: Timestamp of last update

**Unique Constraint:** `(org_id, policy_id)` - One optimization profile per org+policy combination

## Analysis Logic

The engine analyzes the last 30 days of `ai_cost_analytics` data and makes recommendations based on:

### 1. Cost Optimization
- **Trigger:** Cost is high (> $0.001 per request) but latency is acceptable (≤ 2000ms)
- **Recommendation:** Cheaper model (cost-optimized)

### 2. Latency Optimization
- **Trigger:** Latency is high (> 2000ms)
- **Recommendation:** Faster model (latency-optimized)

### 3. Accuracy Optimization
- **Trigger:** Drift frequency is high (> 5%)
- **Recommendation:** Higher accuracy model (accuracy-optimized)

### 4. Budget Optimization
- **Trigger:** Budget utilization > 80%
- **Recommendation:** Cost-optimized model

### 5. Balanced Recommendation
- **Default:** When no specific optimization is needed
- **Recommendation:** Balanced model (good cost/performance trade-off)

## API Endpoint

### Model Optimization Recommendations

**Endpoint:** `GET /api/v1/ai/governance/model-optimization-recommendations`

**Query Parameters:**
- `policy_id` (optional): Policy ID to filter by specific policy

**Authentication:** Required (JWT or service-to-service)

**Example Request:**
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/ai/governance/model-optimization-recommendations"
```

**Example Request (Specific Policy):**
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/ai/governance/model-optimization-recommendations?policy_id=1"
```

**Example Response:**
```json
{
  "org_id": "org-financial-001",
  "recommendations": [
    {
      "org_id": "org-financial-001",
      "policy_id": 1,
      "recommended_model": "mistral:7b-instruct",
      "avg_cost_per_request": 0.0009,
      "avg_latency_ms": 850.5,
      "drift_frequency": 0.02,
      "budget_utilization_percent": null
    },
    {
      "org_id": "org-financial-001",
      "policy_id": null,
      "recommended_model": "mistral:7b-instruct",
      "avg_cost_per_request": 0.0008,
      "avg_latency_ms": 920.0,
      "drift_frequency": 0.01,
      "budget_utilization_percent": null
    }
  ]
}
```

## Drift Frequency Calculation

Drift frequency is calculated from `audit_logs` by:
1. Counting total requests in last 30 days for org+policy
2. Counting requests with `drift_status = "DRIFT_DETECTED"` in payload
3. Calculating: `drift_frequency = drift_requests / total_requests`

## Performance Analysis

The engine analyzes:
- **Average Cost:** From `ai_cost_analytics.estimated_cost_usd`
- **Average Latency:** From `ai_cost_analytics.latency_ms`
- **Request Count:** Minimum 10 requests required for analysis
- **Time Window:** Last 30 days

## Model Recommendations

Currently configured models (can be extended):
- `cost_optimized`: "mistral:7b-instruct" (lower cost)
- `latency_optimized`: "mistral:7b-instruct" (fast inference)
- `accuracy_optimized`: "mistral:7b-instruct" (higher accuracy, can be upgraded)
- `balanced`: "mistral:7b-instruct" (balanced cost/performance)

**Note:** Model recommendations can be extended with actual model performance data and pricing from different providers.

## Thresholds

Configurable thresholds in `app/optimization/engine.py`:
- `COST_HIGH_THRESHOLD`: 0.001 (USD per request)
- `LATENCY_HIGH_THRESHOLD`: 2000.0 (milliseconds)
- `DRIFT_FREQUENCY_HIGH_THRESHOLD`: 0.05 (5%)
- `BUDGET_UTILIZATION_WARNING`: 80.0 (80%)

## Use Cases

### Enterprise Billing Optimization
- Identify high-cost policies and recommend cost-optimized models
- Track cost per policy configuration
- Enable budget-aware model selection

### Performance Optimization
- Identify slow policies and recommend faster models
- Monitor latency trends per policy
- Optimize for SLA compliance

### Quality Assurance
- Identify policies with frequent drift
- Recommend higher accuracy models for critical policies
- Track quality degradation over time

### Budget Management
- Alert when budget utilization exceeds thresholds
- Recommend cost optimizations proactively
- Enable budget-based model selection

## Multi-Tenancy

All optimization profiles are scoped by `org_id`:
- Organizations can only access their own recommendations
- Queries automatically filter by authenticated organization
- No cross-tenant data leakage

## Files Created/Modified

1. `app/db/models.py` - Added `AIModelOptimizationProfile` model
2. `app/optimization/engine.py` - Model optimization engine
3. `app/optimization/__init__.py` - Module init
4. `app/main.py` - Added optimization recommendations endpoint

## Integration

The optimization engine:
- **Non-blocking:** Analysis runs on-demand via API
- **Automatic Updates:** Profiles are refreshed when recommendations are requested
- **Data-Driven:** Uses actual analytics data from last 30 days
- **Policy-Aware:** Provides recommendations per policy configuration

## Future Enhancements

- Integration with actual model performance benchmarks
- Support for multiple model providers
- Budget tracking and alerts
- Automated model switching based on recommendations
- Historical model performance comparison
- A/B testing framework for model recommendations

