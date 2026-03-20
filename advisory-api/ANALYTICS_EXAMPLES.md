# Policy-Aware Performance and Cost Analytics

## Overview

The analytics system tracks AI usage, cost, and performance metrics per policy configuration, enabling enterprise billing and SLA enforcement per policy tier.

## Database Schema

### `ai_cost_analytics` Table

**Key Fields:**
- `org_id`: Organization ID (multi-tenancy isolation)
- `endpoint`: Endpoint name (default: "analyze")
- `policy_id`: Policy profile ID (NULL for default policy)
- `policy_risk_tolerance`: Policy risk tolerance setting
- `policy_verbosity`: Policy verbosity setting
- `policy_compliance_mode`: Policy compliance mode
- `tokens_used`: Total tokens (input + output)
- `input_tokens`: Input tokens
- `output_tokens`: Output tokens
- `estimated_cost_usd`: Estimated cost in USD
- `latency_ms`: Total request latency
- `llm_latency_ms`: LLM-only latency
- `success`: Request status ("success", "failure", "error")
- `correlation_id`: Request correlation ID
- `created_at`: Timestamp

**Index:** `(org_id, endpoint, policy_id)` for efficient querying

## API Endpoints

### 1. Policy Cost Summary

**Endpoint:** `GET /api/v1/ai/governance/policy-cost-summary`

**Query Parameters:**
- `endpoint` (optional): Endpoint name (default: "analyze")
- `month` (optional): Month number 1-12 (defaults to current month)
- `year` (optional): Year (defaults to current year)

**Example Request:**
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/ai/governance/policy-cost-summary?month=1&year=2026"
```

**Example Response:**
```json
{
  "org_id": "org-financial-001",
  "endpoint": "analyze",
  "month": 1,
  "year": 2026,
  "summaries": [
    {
      "policy_id": 1,
      "policy_risk_tolerance": "medium",
      "policy_verbosity": "balanced",
      "policy_compliance_mode": "soc2",
      "total_tokens": 1250000,
      "total_input_tokens": 750000,
      "total_output_tokens": 500000,
      "total_cost_usd": 0.225,
      "request_count": 250,
      "avg_tokens_per_request": 5000,
      "avg_cost_per_request_usd": 0.0009
    },
    {
      "policy_id": null,
      "policy_risk_tolerance": null,
      "policy_verbosity": null,
      "policy_compliance_mode": null,
      "total_tokens": 500000,
      "total_input_tokens": 300000,
      "total_output_tokens": 200000,
      "total_cost_usd": 0.09,
      "request_count": 100,
      "avg_tokens_per_request": 5000,
      "avg_cost_per_request_usd": 0.0009
    }
  ],
  "total_cost_usd": 0.315,
  "total_tokens": 1750000,
  "total_requests": 350
}
```

### 2. Policy Latency Summary

**Endpoint:** `GET /api/v1/ai/governance/policy-latency-summary`

**Query Parameters:**
- `endpoint` (optional): Endpoint name (default: "analyze")
- `month` (optional): Month number 1-12 (defaults to current month)
- `year` (optional): Year (defaults to current year)

**Example Request:**
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/ai/governance/policy-latency-summary?month=1&year=2026"
```

**Example Response:**
```json
{
  "org_id": "org-financial-001",
  "endpoint": "analyze",
  "month": 1,
  "year": 2026,
  "summaries": [
    {
      "policy_id": 1,
      "policy_risk_tolerance": "medium",
      "policy_verbosity": "balanced",
      "policy_compliance_mode": "soc2",
      "avg_latency_ms": 1250.5,
      "avg_llm_latency_ms": 1100.2,
      "min_latency_ms": 850.0,
      "max_latency_ms": 2100.0,
      "request_count": 250
    },
    {
      "policy_id": null,
      "policy_risk_tolerance": null,
      "policy_verbosity": null,
      "policy_compliance_mode": null,
      "avg_latency_ms": 1200.0,
      "avg_llm_latency_ms": 1050.0,
      "min_latency_ms": 800.0,
      "max_latency_ms": 2000.0,
      "request_count": 100
    }
  ]
}
```

### 3. Policy Success Summary

**Endpoint:** `GET /api/v1/ai/governance/policy-success-summary`

**Query Parameters:**
- `endpoint` (optional): Endpoint name (default: "analyze")
- `month` (optional): Month number 1-12 (defaults to current month)
- `year` (optional): Year (defaults to current year)

**Example Request:**
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/ai/governance/policy-success-summary?month=1&year=2026"
```

**Example Response:**
```json
{
  "org_id": "org-financial-001",
  "endpoint": "analyze",
  "month": 1,
  "year": 2026,
  "summaries": [
    {
      "policy_id": 1,
      "policy_risk_tolerance": "medium",
      "policy_verbosity": "balanced",
      "policy_compliance_mode": "soc2",
      "total_requests": 250,
      "success_count": 245,
      "failure_count": 3,
      "error_count": 2,
      "success_rate": 98.0,
      "failure_rate": 1.2,
      "error_rate": 0.8
    },
    {
      "policy_id": null,
      "policy_risk_tolerance": null,
      "policy_verbosity": null,
      "policy_compliance_mode": null,
      "total_requests": 100,
      "success_count": 98,
      "failure_count": 1,
      "error_count": 1,
      "success_rate": 98.0,
      "failure_rate": 1.0,
      "error_rate": 1.0
    }
  ]
}
```

## Cost Estimation

The system estimates costs based on token usage:
- **Input tokens:** $0.10 per 1M tokens
- **Output tokens:** $0.30 per 1M tokens

These rates can be adjusted in `app/analytics/service.py`:
```python
COST_PER_MILLION_INPUT_TOKENS = 0.10
COST_PER_MILLION_OUTPUT_TOKENS = 0.30
```

## Integration

Analytics are automatically recorded for every request:
- **Success:** Recorded after successful advisory generation
- **Failure:** Recorded for validation errors, database errors, and internal errors
- **Non-blocking:** Analytics recording failures don't block requests

## Use Cases

### Enterprise Billing
- Track monthly costs per policy configuration
- Generate invoices based on policy tier usage
- Identify cost drivers by policy settings

### SLA Enforcement
- Monitor latency per policy tier
- Track success rates per policy configuration
- Alert on SLA violations

### Policy Optimization
- Compare cost and performance across policy configurations
- Identify optimal policy settings for cost/performance balance
- Analyze impact of policy changes on usage patterns

## Multi-Tenancy

All analytics are scoped by `org_id`:
- Organizations can only access their own analytics
- Queries automatically filter by authenticated organization
- No cross-tenant data leakage

## Files Modified/Created

1. `app/db/models.py` - Added `AICostAnalytics` model
2. `app/analytics/service.py` - Analytics recording and querying service
3. `app/analytics/__init__.py` - Module init
4. `app/ollama_client.py` - Enhanced to return token usage
5. `app/advisory_engine.py` - Updated to return token usage
6. `app/main.py` - Integrated analytics recording and endpoints

