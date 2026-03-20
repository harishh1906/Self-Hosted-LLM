# Explainable AI Serving

## Overview

Extended the AI advisory service to support explainable AI serving with comprehensive decision logging, force model override, and control plane health summaries.

## Features

### 1. Explainable Decision Logging

**Fields Logged:**
- `decision_reason`: Reason for model/policy decision (provided or auto-generated)
- `active_model`: Primary model selected
- `fallback_model`: Fallback model available
- `policy_id`: Policy profile ID used
- `correlation_id`: Request correlation ID

**Auto-Generated Decision Reason:**
If `decision_reason` is not provided, it's automatically generated from the model selection chain:
```
"Model selected via: force_model:claude-3-5-sonnet"
"Model selected via: model_override:mistral:7b-instruct -> org_config:claude-3-5-sonnet"
```

**Example Log:**
```json
{
  "level": "INFO",
  "message": "Model selection decision (explainable AI)",
  "correlation_id": "abc-123-def-456",
  "org_id": "org-financial-001",
  "policy_id": 1,
  "selected_model": "claude-3-5-sonnet",
  "primary_model": "claude-3-5-sonnet",
  "fallback_model": "mistral:7b-instruct",
  "decision_reason": "Model selected via: force_model:claude-3-5-sonnet",
  "force_model": "claude-3-5-sonnet"
}
```

**Audit Payload:**
```json
{
  "decision_reason": "Model selected via: force_model:claude-3-5-sonnet",
  "active_model": "claude-3-5-sonnet",
  "fallback_model": "mistral:7b-instruct",
  "actual_model_used": "claude-3-5-sonnet",
  "policy_id": 1,
  "correlation_id": "abc-123-def-456"
}
```

### 2. Force Model Override

**New Field:** `force_model` in `FindingInput`

**Behavior:**
- When `force_model` is present, it's used as the primary model
- **Fallback still allowed** - if force_model fails, falls back to default MODEL_NAME
- Highest priority in model selection (above model_override)

**Priority Order:**
1. `force_model` (highest priority, fallback allowed)
2. `model_override`
3. `active_model` (from request payload)
4. Organization-specific config
5. Default model

**Example Request:**
```json
{
  "title": "SQL Injection Vulnerability",
  "description": "User input is not sanitized...",
  "severity": "High",
  "org_id": "org-financial-001",
  "force_model": "claude-3-5-sonnet",
  "decision_reason": "High-severity finding requires high-accuracy model"
}
```

**Logging:**
```json
{
  "level": "INFO",
  "message": "Force model override applied (fallback still allowed)",
  "correlation_id": "abc-123-def-456",
  "org_id": "org-financial-001",
  "force_model": "claude-3-5-sonnet",
  "fallback_model": "mistral:7b-instruct"
}
```

### 3. Model Health Summary Endpoint

**Endpoint:** `GET /internal/control-plane/model-health-summary`

**Response Fields:**
- `model_name`: Model identifier
- `usage_count`: Total number of requests
- `avg_latency_ms`: Average request latency
- `fallback_count`: Number of fallback events
- `drift_adjustments`: Number of drift adjustments
- `last_used_at`: ISO timestamp of last usage
- `sla_violations`: Number of SLA violations (latency > 2000ms)
- `confidence_trend`: Confidence trend information

**Example Response:**
```json
{
  "models": [
    {
      "model_name": "mistral:7b-instruct",
      "usage_count": 1250,
      "avg_latency_ms": 1250.5,
      "fallback_count": 2,
      "drift_adjustments": 15,
      "last_used_at": "2026-01-15T10:30:00Z",
      "sla_violations": 5,
      "confidence_trend": {
        "recent_avg": 0.75,
        "older_avg": 0.80,
        "drop_percent": 6.25,
        "is_declining": false,
        "sample_count": 100
      }
    },
    {
      "model_name": "claude-3-5-sonnet",
      "usage_count": 850,
      "avg_latency_ms": 1850.2,
      "fallback_count": 0,
      "drift_adjustments": 8,
      "last_used_at": "2026-01-15T10:29:45Z",
      "sla_violations": 12,
      "confidence_trend": {
        "recent_avg": 0.82,
        "older_avg": 0.85,
        "drop_percent": 3.53,
        "is_declining": false,
        "sample_count": 85
      }
    }
  ]
}
```

**Confidence Trend:**
- `recent_avg`: Average confidence from last 10 requests
- `older_avg`: Average confidence from previous 10 requests
- `drop_percent`: Percentage drop in confidence
- `is_declining`: True if drop > 10%
- `sample_count`: Total confidence samples tracked

## Implementation Details

### Model Selection Priority

**Complete Priority Chain:**
```
1. force_model (if provided) → fallback to MODEL_NAME if fails
2. model_override (if provided)
3. active_model (from request payload)
4. Organization-specific config (from model manager)
5. Default model (from model manager)
```

### Decision Reason Generation

**Auto-Generation:**
```python
if not finding.decision_reason:
    decision_reason = f"Model selected via: {' -> '.join(model_selection_reason)}"
```

**Manual Override:**
- Scanner can provide `decision_reason` for custom explanations
- Used as-is if provided
- Max length: 500 characters

### SLA Violation Tracking

**Definition:**
- SLA violation occurs when `latency_ms > 2000ms` (SLA_LATENCY_THRESHOLD)
- Tracked per model in `ModelHealthTracker`
- Incremented on each violation

**Usage:**
- Included in model health summary
- Helps identify models with performance issues
- Supports capacity planning

### Confidence Trend Analysis

**Calculation:**
- Maintains rolling history (last 100 values per model)
- Compares recent window (last 10) vs older window (previous 10)
- Calculates drop percentage
- Flags declining trends (> 10% drop)

**Use Cases:**
- Identify models with quality degradation
- Trigger self-healing mechanisms
- Support model optimization decisions

## Use Cases

### 1. Explainable AI Decisions
- Full transparency in model selection
- Decision reason tracking
- Audit trail for compliance
- Debugging and troubleshooting

### 2. Force Model Routing
- Route critical findings to high-accuracy models
- Override default model selection
- Maintain fallback safety
- Support A/B testing

### 3. Control Plane Monitoring
- Comprehensive model health metrics
- SLA violation tracking
- Confidence trend analysis
- Capacity planning support

### 4. Compliance and Audit
- Full decision trail
- Model selection transparency
- Policy application tracking
- Performance monitoring

## Safety Features

- **Fallback Preserved:** Force model still allows fallback
- **Non-Breaking:** Response schema unchanged
- **Auditable:** All decisions logged
- **Transparent:** Decision reasons provided
- **Observable:** Comprehensive health metrics

## Files Created/Modified

1. `app/schemas.py` - Added `force_model` and `decision_reason` fields
2. `app/advisory_engine.py` - Enhanced with force_model support and explainability data
3. `app/model_health.py` - Added SLA violation tracking
4. `app/model_health_summary.py` - New module for control plane health summary
5. `app/main.py` - Added model-health-summary endpoint and enhanced logging

## Production Readiness

✅ **Explainable Decisions:** Full decision reason tracking  
✅ **Force Model Override:** Priority-based routing with fallback  
✅ **Comprehensive Logging:** All required fields logged  
✅ **Control Plane Summary:** Complete health metrics endpoint  
✅ **Non-Breaking:** Response schema unchanged  

