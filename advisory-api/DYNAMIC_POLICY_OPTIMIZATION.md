# Dynamic Policy and Model Optimization

## Overview

Extended the AI advisory service to support dynamic policy and model optimization from scanners, enabling real-time policy adjustments and model routing.

## Features

### 1. Optimized Policy Instructions from Scanner

**New Fields in FindingInput:**
- `risk_tolerance`: Override risk tolerance (low|medium|high)
- `verbosity`: Override verbosity (concise|balanced|detailed)
- `remediation_style`: Override remediation style (practical|strict|educational)
- `model_override`: Override model selection (routes to specified model)

**Validation:**
- All fields are validated against allowed values
- Invalid values raise validation errors

**Example Request:**
```json
{
  "title": "SQL Injection Vulnerability",
  "description": "User input is not sanitized...",
  "severity": "High",
  "org_id": "org-financial-001",
  "risk_tolerance": "low",
  "verbosity": "detailed",
  "remediation_style": "strict",
  "model_override": "claude-3-5-sonnet"
}
```

### 2. Model Override Routing

**Priority Order:**
1. `model_override` (from scanner) - **Highest Priority**
2. `active_model` (from request payload)
3. Organization-specific config (from model manager)
4. Default model (from model manager)

**Behavior:**
- When `model_override` is present, it routes advisory generation to that model
- Overrides all other model selection logic
- Logged for auditability

**Logging:**
```json
{
  "level": "INFO",
  "message": "Model override from scanner applied",
  "correlation_id": "abc-123-def-456",
  "org_id": "org-financial-001",
  "model_override": "claude-3-5-sonnet"
}
```

### 3. Comprehensive Logging

**Applied Policy Parameters:**
- Logged when scanner provides optimized policy instructions
- Includes all overridden parameters
- Preserves original policy ID for reference

**Example Log:**
```json
{
  "level": "INFO",
  "message": "Optimized policy parameters applied from scanner",
  "correlation_id": "abc-123-def-456",
  "org_id": "org-financial-001",
  "applied_policy_params": {
    "risk_tolerance": "low",
    "verbosity": "detailed",
    "remediation_style": "strict"
  },
  "original_policy_id": 1
}
```

**Model Selection:**
- Selected model logged with full decision chain
- Includes whether fallback was used
- Includes whether degradation was applied

**Degradation Tracking:**
- Tracks if verbosity degradation was applied
- Tracks if severity sensitivity reduction was applied
- Included in audit payload

**Audit Payload:**
```json
{
  "applied_policy_params": {
    "risk_tolerance": "low",
    "verbosity": "detailed"
  },
  "degradation_used": false,
  "used_fallback": false,
  "model_selection_decision": {
    "selected_model": "claude-3-5-sonnet",
    "primary_model": "claude-3-5-sonnet",
    "used_fallback": false,
    "fallback_model": null,
    "selection_timestamp": "2026-01-15T10:30:00Z"
  }
}
```

### 4. Policy Effectiveness Endpoint

**Endpoint:** `GET /internal/policy-effectiveness`

**Response Fields:**
- `policy_id`: Policy profile ID
- `avg_confidence`: Average confidence score (from audit logs)
- `avg_latency`: Average request latency (from analytics)
- `drift_frequency`: Frequency of drift detection (0.0-1.0)
- `tenant_rating_average`: Average tenant rating (1.0-5.0)

**Example Response:**
```json
{
  "policies": [
    {
      "policy_id": 1,
      "org_id": "org-financial-001",
      "avg_confidence": 0.85,
      "avg_latency": 1350.5,
      "drift_frequency": 0.05,
      "tenant_rating_average": 4.2,
      "request_count": 500
    },
    {
      "policy_id": 2,
      "org_id": "org-healthcare-001",
      "avg_confidence": 0.78,
      "avg_latency": 1850.2,
      "drift_frequency": 0.12,
      "tenant_rating_average": 3.8,
      "request_count": 300
    }
  ]
}
```

**Metrics Calculation:**
- **avg_confidence**: Average from audit logs (30-day window)
- **avg_latency**: Average from analytics (30-day window)
- **drift_frequency**: Drift events / total requests (30-day window)
- **tenant_rating_average**: Average from analytics where tenant_rating is not null (30-day window)

## Implementation Details

### Policy Parameter Application

**Override Logic:**
```python
# Load base policy
policy = load_policy(org_id)

# Apply scanner overrides (if provided)
if finding.risk_tolerance:
    policy["risk_tolerance"] = finding.risk_tolerance
if finding.verbosity:
    policy["verbosity"] = finding.verbosity
if finding.remediation_style:
    policy["remediation_style"] = finding.remediation_style
```

**Model Override Logic:**
```python
# Priority: model_override > active_model > org_config > default
if finding.model_override:
    model_to_use = finding.model_override  # Highest priority
elif active_model:
    model_to_use = active_model
elif org_config:
    model_to_use = org_config
else:
    model_to_use = default
```

### Database Schema Updates

**AICostAnalytics:**
- Added `tenant_rating` column (Float, nullable)
- Stores tenant ratings (1.0-5.0) for policy effectiveness tracking

**Migration:**
```sql
ALTER TABLE ai_cost_analytics 
ADD COLUMN tenant_rating FLOAT;
```

## Use Cases

### 1. Scanner-Driven Optimization
- Scanners can optimize policy per finding
- Adjust verbosity based on finding severity
- Route to specific models for critical findings
- Apply strict remediation for high-risk scenarios

### 2. Policy Performance Analysis
- Track policy effectiveness metrics
- Compare policy configurations
- Identify optimal policy settings
- Monitor tenant satisfaction

### 3. Dynamic Model Selection
- Route critical findings to high-accuracy models
- Use cost-effective models for low-severity findings
- Optimize based on scanner recommendations
- Maintain fallback capabilities

### 4. Compliance and Audit
- Full audit trail of policy applications
- Track model selection decisions
- Monitor degradation usage
- Analyze policy effectiveness

## Safety Features

- **Validation:** All policy parameters validated
- **Non-Breaking:** Response schema unchanged
- **Auditable:** All decisions logged
- **Fallback:** Model override still supports fallback
- **Degradation:** Automatic degradation still applies
- **Multi-Tenant:** Policy overrides scoped by org_id

## Files Created/Modified

1. `app/schemas.py` - Added optimized policy fields with validation
2. `app/advisory_engine.py` - Enhanced with policy override and model_override routing
3. `app/policy_effectiveness.py` - New module for policy effectiveness analysis
4. `app/main.py` - Added policy-effectiveness endpoint and enhanced logging
5. `app/db/models.py` - Added tenant_rating column to AICostAnalytics

## Production Readiness

✅ **Dynamic Policy:** Scanner-driven policy optimization  
✅ **Model Override:** Priority-based model routing  
✅ **Comprehensive Logging:** All decisions tracked  
✅ **Effectiveness Metrics:** Policy performance analysis  
✅ **Non-Breaking:** Response schema unchanged  

