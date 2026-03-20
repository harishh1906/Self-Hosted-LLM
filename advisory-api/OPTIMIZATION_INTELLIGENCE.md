# Optimization Intelligence Endpoint

## Overview

The optimization intelligence endpoint provides comprehensive insights into model performance, policy effectiveness, and decision-making patterns. This is a read-only endpoint that does not affect advisory responses.

## Endpoint

**GET `/internal/optimization-insights`**

**Access:** Internal only (no authentication required for internal endpoints)

**Response Time:** Typically < 500ms (depends on data volume)

## Response Structure

### 1. Top Performing Models

Models ranked by performance score (latency + fallback rate).

**Ranking Algorithm:**
- Performance Score = `latency_score * (1 - fallback_rate)`
- `latency_score` = `1.0 / (1.0 + avg_latency_ms / 1000.0)` (normalized, lower latency = higher score)
- `fallback_rate` = `fallback_count / total_requests` (penalty factor)
- Range: 0.0 (worst) to 1.0 (best)

**Fields:**
- `model_name`: Model identifier
- `avg_latency_ms`: Average request latency (milliseconds)
- `fallback_rate`: Rate of fallback events (0.0-1.0)
- `drift_adjustment_rate`: Rate of drift adjustments (0.0-1.0)
- `total_requests`: Total number of requests (minimum 10 for ranking)
- `performance_score`: Combined performance score (0.0-1.0)
- `rank`: Ranking position (1 = best)

**Example:**
```json
{
  "top_performing_models": [
    {
      "model_name": "mistral:7b-instruct",
      "avg_latency_ms": 1250.5,
      "fallback_rate": 0.002,
      "drift_adjustment_rate": 0.012,
      "total_requests": 1250,
      "performance_score": 0.998,
      "rank": 1
    },
    {
      "model_name": "claude-3-5-sonnet",
      "avg_latency_ms": 1850.2,
      "fallback_rate": 0.001,
      "drift_adjustment_rate": 0.008,
      "total_requests": 850,
      "performance_score": 0.996,
      "rank": 2
    }
  ]
}
```

### 2. Fallback Usage Statistics

Overall fallback statistics across all models.

**Fields:**
- `total_fallbacks`: Total number of fallback events
- `total_requests`: Total number of requests
- `overall_fallback_rate`: Overall fallback rate (0.0-1.0)
- `models_with_fallbacks`: List of models that experienced fallbacks

**Example:**
```json
{
  "fallback_usage_stats": {
    "total_fallbacks": 5,
    "total_requests": 2500,
    "overall_fallback_rate": 0.002,
    "models_with_fallbacks": [
      {
        "model_name": "claude-3-5-sonnet",
        "fallback_count": 3,
        "fallback_rate": 0.0035
      },
      {
        "model_name": "mistral:7b-instruct",
        "fallback_count": 2,
        "fallback_rate": 0.0016
      }
    ]
  }
}
```

### 3. Drift Adjustment Trends

Drift detection trends over the last 30 days.

**Fields:**
- `total_drift_events`: Total number of drift events detected
- `events_by_date`: Drift events grouped by date (ISO format)
- `avg_events_per_day`: Average drift events per day

**Example:**
```json
{
  "drift_adjustment_trends": {
    "total_drift_events": 45,
    "events_by_date": {
      "2026-01-15": 2,
      "2026-01-14": 3,
      "2026-01-13": 1,
      "2026-01-12": 2
    },
    "avg_events_per_day": 1.5
  }
}
```

### 4. Policy Profile Effectiveness

Policy configuration effectiveness metrics grouped by policy profile.

**Grouping:**
- `risk_tolerance`: low|medium|high
- `verbosity`: concise|balanced|detailed
- `compliance_mode`: none|soc2|iso|hipaa

**Fields:**
- `risk_tolerance`: Risk tolerance setting
- `verbosity`: Verbosity setting
- `compliance_mode`: Compliance mode setting
- `avg_latency_ms`: Average request latency (milliseconds)
- `request_count`: Total number of requests
- `success_rate`: Success rate (0.0-1.0)

**Sorting:** By success rate (descending), then by latency (ascending)

**Example:**
```json
{
  "policy_profile_effectiveness": [
    {
      "risk_tolerance": "high",
      "verbosity": "detailed",
      "compliance_mode": "strict",
      "avg_latency_ms": 1350.2,
      "request_count": 500,
      "success_rate": 0.98
    },
    {
      "risk_tolerance": "medium",
      "verbosity": "balanced",
      "compliance_mode": "none",
      "avg_latency_ms": 1200.5,
      "request_count": 1200,
      "success_rate": 0.97
    }
  ]
}
```

### 5. Model Selection Decision Chains

Model selection decision chain for the last 100 requests (most recent first).

**Fields:**
- `correlation_id`: Request correlation ID
- `org_id`: Organization ID
- `policy_id`: Policy profile ID
- `timestamp`: Request timestamp (ISO format)
- `selected_model`: Model that was selected
- `primary_model`: Primary model attempted
- `fallback_model`: Fallback model available
- `actual_model_used`: Model actually used (primary or fallback)
- `used_fallback`: Whether fallback was used (boolean)
- `force_model`: Force model override (if provided)
- `model_override`: Model override from scanner (if provided)
- `decision_reason`: Reason for model selection
- `applied_policy_params`: Policy parameters applied from scanner
- `response_time_ms`: Request response time (milliseconds)
- `model_confidence`: Model confidence score

**Example:**
```json
{
  "model_selection_decision_chains": [
    {
      "correlation_id": "req-abc-123-def-456",
      "org_id": "org-financial-001",
      "policy_id": 1,
      "timestamp": "2026-01-15T10:30:00Z",
      "selected_model": "mistral:7b-instruct",
      "primary_model": "mistral:7b-instruct",
      "fallback_model": "mistral:7b-instruct",
      "actual_model_used": "mistral:7b-instruct",
      "used_fallback": false,
      "force_model": null,
      "model_override": null,
      "decision_reason": "Model selected via: default:mistral:7b-instruct",
      "applied_policy_params": {
        "risk_tolerance": "low",
        "verbosity": "detailed"
      },
      "response_time_ms": 1250.5,
      "model_confidence": 0.85
    },
    {
      "correlation_id": "req-xyz-789-abc-012",
      "org_id": "org-financial-001",
      "policy_id": 1,
      "timestamp": "2026-01-15T10:29:45Z",
      "selected_model": "claude-3-5-sonnet",
      "primary_model": "claude-3-5-sonnet",
      "fallback_model": "mistral:7b-instruct",
      "actual_model_used": "mistral:7b-instruct",
      "used_fallback": true,
      "force_model": "claude-3-5-sonnet",
      "model_override": null,
      "decision_reason": "High-severity finding requires high-accuracy model",
      "applied_policy_params": {
        "risk_tolerance": "low"
      },
      "response_time_ms": 1850.2,
      "model_confidence": 0.82
    }
  ]
}
```

## Complete Response Example

```json
{
  "top_performing_models": [...],
  "fallback_usage_stats": {...},
  "drift_adjustment_trends": {...},
  "policy_profile_effectiveness": [...],
  "model_selection_decision_chains": [...]
}
```

## Data Sources

1. **Model Health Tracker** - Real-time model health metrics (latency, fallback counts)
2. **Audit Logs** - Drift events and model selection decisions
3. **Cost Analytics** - Policy profile effectiveness metrics

## Time Windows

- **Top Performing Models:** All-time (minimum 10 requests per model)
- **Fallback Usage Stats:** All-time
- **Drift Adjustment Trends:** Last 30 days
- **Policy Profile Effectiveness:** Last 30 days
- **Model Selection Decision Chains:** Last 100 requests (most recent first)

## Performance Considerations

- **Caching:** Consider implementing caching for frequently accessed insights
- **Pagination:** Model selection decision chains limited to 100 most recent
- **Database Queries:** Optimized with indexes on `created_at` and JSONB fields
- **Response Size:** Typically < 100KB (depends on data volume)

## Privacy and Security

- **No Advisory Content:** Endpoint returns only metrics and decision metadata
- **No Sensitive Data:** Only performance and configuration data
- **Internal Only:** Endpoint is internal and not exposed to external clients
- **Audit Trail:** All data is traceable via correlation_id

## Use Cases

1. **Performance Monitoring:** Track model performance trends
2. **Policy Optimization:** Identify most effective policy configurations
3. **Model Selection:** Understand decision-making patterns
4. **Drift Detection:** Monitor quality degradation trends
5. **Capacity Planning:** Analyze fallback usage and model reliability

## Error Handling

If an error occurs, the endpoint returns empty arrays/objects with default values:

```json
{
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
```

## Implementation Details

**File:** `app/performance_intelligence.py`

**Function:** `get_optimization_insights()`

**Endpoint:** `app/main.py` - `GET /internal/optimization-insights`

**Dependencies:**
- `model_health_tracker` - Real-time model health metrics
- `AuditLog` - Audit log entries for drift and decisions
- `AICostAnalytics` - Policy profile effectiveness metrics

## Production Readiness

✅ **Read-Only:** Does not affect advisory responses  
✅ **Comprehensive:** All required metrics included  
✅ **Performance:** Optimized queries with proper indexes  
✅ **Error Handling:** Graceful degradation on errors  
✅ **Privacy Safe:** No advisory content exposed  

