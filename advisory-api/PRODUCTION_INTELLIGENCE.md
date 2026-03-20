# Production Intelligence Feedback Loops

## Overview

Enhanced the AI advisory service with production intelligence feedback loops that continuously evaluate model performance, automatically adjust behavior, and provide optimization insights.

## Features

### 1. Continuous Model Performance Evaluation

**Trend Analysis:**
- **Confidence Trends:** Tracks confidence values over time per model
- **Latency Trends:** Monitors average latency per model
- **Drift Trends:** Tracks drift adjustment frequency per model

**Performance Intelligence:**
- Maintains rolling history of confidence values (last 100 per model)
- Calculates confidence drop trends (recent vs older averages)
- Identifies declining performance patterns

**Example Trend Detection:**
```python
# Confidence trend analysis
recent_avg = 0.65  # Last 10 requests
older_avg = 0.75   # Previous 10 requests
drop_percent = 13.3%  # Significant drop detected
```

### 2. Automatic Verbosity Adjustment on SLA Violations

**Enhanced Behavior:**
- **SLA-Based Degradation:** When latency > 2000ms, automatically reduces verbosity
- **Self-Healing Degradation:** When confidence drops repeatedly, reduces verbosity
- **Degradation Path:** `detailed` → `balanced` → `concise`

**Logging:**
```json
{
  "level": "INFO",
  "message": "Load-aware verbosity degradation (SLA violation)",
  "correlation_id": "abc-123-def-456",
  "org_id": "org-financial-001",
  "model_name": "claude-3-5-sonnet",
  "original_verbosity": "detailed",
  "degraded_verbosity": "balanced",
  "avg_latency_ms": 2150.5,
  "sla_threshold_ms": 2000.0
}
```

### 3. Optimization Insights Endpoint

**Endpoint:** `GET /internal/optimization-insights`

**Response Fields:**

#### top_performing_models
Models ranked by performance score (latency and fallback rate):
```json
{
  "top_performing_models": [
    {
      "model_name": "mistral:7b-instruct",
      "avg_latency_ms": 1250.5,
      "fallback_rate": 0.02,
      "drift_adjustment_rate": 0.05,
      "total_requests": 500,
      "performance_score": 0.95
    }
  ]
}
```

#### fallback_usage_stats
Overall fallback statistics:
```json
{
  "fallback_usage_stats": {
    "total_fallbacks": 15,
    "total_requests": 1250,
    "overall_fallback_rate": 0.012,
    "models_with_fallbacks": [
      {
        "model_name": "claude-3-5-sonnet",
        "fallback_count": 10,
        "fallback_rate": 0.05
      }
    ]
  }
}
```

#### drift_adjustment_trends
Drift detection trends over time:
```json
{
  "drift_adjustment_trends": {
    "total_drift_events": 42,
    "events_by_date": {
      "2026-01-15": 3,
      "2026-01-16": 5,
      "2026-01-17": 2
    },
    "avg_events_per_day": 1.4
  }
}
```

#### policy_profile_effectiveness
Policy configuration effectiveness metrics:
```json
{
  "policy_profile_effectiveness": [
    {
      "risk_tolerance": "medium",
      "verbosity": "balanced",
      "compliance_mode": "soc2",
      "avg_latency_ms": 1350.2,
      "request_count": 500,
      "success_rate": 0.98
    }
  ]
}
```

### 4. Self-Healing Behavior

**Trigger Conditions:**
- Confidence drop > 10% over last 10 requests
- Compares recent average vs older average

**Self-Healing Actions:**
1. **Reduce Verbosity:** Automatically downgrades verbosity level
2. **Reduce Severity Sensitivity:** Downgrades severity by one level (Critical → High → Medium → Low)

**Example:**
```
Model: claude-3-5-sonnet
Recent Confidence Avg: 0.65
Older Confidence Avg: 0.75
Drop: 13.3% (> 10% threshold)

Actions:
- Verbosity: detailed → balanced
- Severity Sensitivity: Critical → High, High → Medium, etc.
```

**Logging:**
```json
{
  "level": "WARNING",
  "message": "Self-healing triggered (confidence drop detected)",
  "correlation_id": "abc-123-def-456",
  "org_id": "org-financial-001",
  "model_name": "claude-3-5-sonnet",
  "confidence_drop_percent": 13.3,
  "original_verbosity": "detailed",
  "adjusted_verbosity": "balanced",
  "severity_sensitivity_reduction": 0.1
}
```

### 5. Comprehensive Model Selection Logging

**All Model Selection Decisions Logged:**
- Selected model
- Primary model attempted
- Fallback usage
- Selection reason chain
- Timestamp

**Logging Locations:**
1. **Structured Logs:** Model selection decision with full context
2. **Audit Payload:** Model selection decision included in audit log

**Example Log:**
```json
{
  "level": "INFO",
  "message": "Model selection decision",
  "correlation_id": "abc-123-def-456",
  "org_id": "org-financial-001",
  "selected_model": "mistral:7b-instruct",
  "selection_reason": "request_payload:claude-3-5-sonnet -> org_config:mistral:7b-instruct",
  "request_active_model": "claude-3-5-sonnet",
  "rollback_flag": false
}
```

**Audit Payload:**
```json
{
  "model_selection_decision": {
    "selected_model": "mistral:7b-instruct",
    "primary_model": "claude-3-5-sonnet",
    "used_fallback": true,
    "fallback_model": "mistral:7b-instruct",
    "selection_timestamp": "2026-01-15T10:30:00Z"
  }
}
```

## Implementation Details

### Performance Intelligence System

**Confidence Tracking:**
- Maintains rolling history per model (last 100 values)
- Calculates trends comparing recent vs older windows
- Triggers self-healing when drop exceeds threshold

**Trend Calculation:**
```python
recent_window = last 10 requests
older_window = previous 10 requests
drop_percent = ((older_avg - recent_avg) / older_avg) * 100
trigger_self_healing = drop_percent > 10%
```

### Self-Healing Logic

**Severity Sensitivity Reduction:**
```python
severity_map = {
    "Critical": "High",
    "High": "Medium",
    "Medium": "Low",
    "Low": "Low"
}
adjusted_severity = severity_map[original_severity]
```

**Verbosity Reduction:**
```python
if original_verbosity == "detailed":
    adjusted_verbosity = "balanced"
elif original_verbosity == "balanced":
    adjusted_verbosity = "concise"
```

### Model Selection Decision Chain

**Priority Order:**
1. Request payload (`active_model` field)
2. Organization-specific config (from model manager)
3. Default model (from model manager)
4. Database lookup (`ai_active_models` table)
5. Default constant (`MODEL_NAME`)

**Decision Logging:**
- Each step in the chain is logged
- Final decision includes full reason chain
- Audit trail preserved in audit log payload

## Configuration

### Self-Healing Thresholds
```python
CONFIDENCE_DROP_THRESHOLD = 0.1  # 10% drop triggers self-healing
CONFIDENCE_DROP_WINDOW = 10  # Check last 10 requests
SEVERITY_SENSITIVITY_REDUCTION = 0.1  # 10% reduction
```

### SLA Threshold
```python
SLA_LATENCY_THRESHOLD_MS = 2000.0  # 2 seconds
```

## Use Cases

### 1. Performance Monitoring
- Track model performance trends
- Identify declining models
- Compare model effectiveness
- Optimize model selection

### 2. Automatic Optimization
- Self-healing on confidence drops
- Load-aware verbosity reduction
- Severity sensitivity adjustment
- Maintain service quality

### 3. Policy Optimization
- Identify effective policy configurations
- Compare policy performance
- Optimize policy settings
- Improve success rates

### 4. Drift Detection
- Track drift frequency trends
- Identify models with frequent drift
- Correlate drift with performance
- Optimize model selection

## Safety Features

- **Non-Breaking:** Response schema unchanged
- **Transparent:** All adjustments logged
- **Auditable:** Full decision trail
- **Reversible:** Self-healing is per-request
- **Configurable:** Thresholds adjustable
- **Observable:** Comprehensive metrics

## Files Created/Modified

1. `app/performance_intelligence.py` - New module for performance tracking and insights
2. `app/advisory_engine.py` - Enhanced with self-healing and enhanced verbosity adjustment
3. `app/main.py` - Added optimization insights endpoint and model selection logging
4. `app/model_health.py` - Already tracks per-model metrics

## Production Readiness

✅ **Continuous Evaluation:** Performance trends tracked per model  
✅ **Automatic Adjustment:** Verbosity and severity sensitivity auto-adjusted  
✅ **Optimization Insights:** Comprehensive insights endpoint  
✅ **Self-Healing:** Automatic recovery from confidence drops  
✅ **Full Auditability:** All decisions logged and tracked  

