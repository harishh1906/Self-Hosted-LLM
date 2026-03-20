# Enterprise Reliability and Compliance Enhancements

## Overview

Enhanced advisory generation with SLA health reporting, drift-based confidence adjustment, and runtime rollback capabilities for enterprise reliability and compliance.

## Features

### 1. SLA Health Reporting

Response time and model confidence are now included in logs for SLA monitoring and compliance.

**Log Fields Added:**
- `response_time_ms`: Total request latency in milliseconds
- `model_confidence`: Final advisory confidence score

**Example Log:**
```json
{
  "correlation_id": "abc-123-def-456",
  "org_id": "org-financial-001",
  "response_time_ms": 1350.2,
  "model_confidence": 0.75,
  "llm_latency_ms": 1250.5,
  "total_latency_ms": 1350.2,
  "drift_status": "STABLE",
  "rollback_flag": false
}
```

### 2. Drift-Based Confidence Adjustment

When drift is detected, the system automatically:
- **Lowers advisory confidence** by 10% (minimum 0.1)
- **Adds fallback notice** to audit payload
- **Logs warning** with drift details

**Confidence Adjustment:**
```python
if drift_status == "DRIFT_DETECTED":
    adjusted_confidence = max(0.1, original_confidence - 0.1)
    # Example: 0.85 → 0.75, 0.50 → 0.40, 0.15 → 0.10
```

**Fallback Notice:**
```
"Drift detected: CONFIDENCE_DROP_7.5%, RISK_SCORE_SHIFT_12_POINTS. Confidence adjusted from 0.85 to 0.75."
```

**Audit Payload:**
```json
{
  "action": "analyze_finding",
  "payload": {
    "confidence": 0.75,
    "drift_status": "DRIFT_DETECTED",
    "drift_reasons": ["CONFIDENCE_DROP_7.5%", "RISK_SCORE_SHIFT_12_POINTS"],
    "fallback_notice": "Drift detected: CONFIDENCE_DROP_7.5%, RISK_SCORE_SHIFT_12_POINTS. Confidence adjusted from 0.85 to 0.75.",
    "response_time_ms": 1350.2,
    "model_confidence": 0.75
  }
}
```

### 3. Advisory Output Structure

**✅ Unchanged:** The advisory response schema remains unchanged. Confidence adjustments and fallback notices are internal and transparent to API consumers.

**Example Response:**
```json
{
  "finding": "SQL Injection Vulnerability",
  "advisory": {
    "risk_summary": "...",
    "business_impact": "...",
    "severity": "High",
    "remediation_steps": [...],
    "confidence": 0.75  // Adjusted if drift detected
  },
  "risk_assessment": {
    "risk_score": 75,
    "risk_level": "High",
    "sla": "72h",
    "justification": "..."
  }
}
```

### 4. Runtime Rollback Trigger

Added `rollback_flag` support to force use of default model instead of active_model.

**Request Schema:**
```python
class FindingInput(BaseModel):
    # ... existing fields ...
    rollback_flag: Optional[bool] = Field(
        None,
        description="If true, use default MODEL_NAME instead of active_model"
    )
```

**Behavior:**
- If `rollback_flag = true`: Uses default `MODEL_NAME` ("mistral:7b-instruct")
- If `rollback_flag = false` or `None`: Uses `active_model` (if provided) or default

**Example Request:**
```json
{
  "title": "SQL Injection Vulnerability",
  "description": "User input is not sanitized...",
  "severity": "High",
  "active_model": "claude-3-5-sonnet",
  "rollback_flag": true,
  "org_id": "org-financial-001"
}
```

**Result:** Advisory generated using default model ("mistral:7b-instruct") despite `active_model` being specified.

## Implementation Details

### Model Selection Priority

1. **Rollback Flag** (Highest Priority)
   - If `rollback_flag = true` → Use default `MODEL_NAME`

2. **Request Payload**
   - If `active_model` in request → Use that model

3. **Database Lookup**
   - Check `ai_active_models` table by `org_id` and `policy_id`

4. **Default Model** (Final Fallback)
   - Use `MODEL_NAME` from `app/ollama_client.py`

### Drift Detection Flow

```
Generate Advisory
    ↓
Detect Drift
    ↓
If DRIFT_DETECTED:
    - Lower confidence by 10% (min 0.1)
    - Create fallback notice
    - Log warning
    ↓
Include in Audit Payload
    ↓
Return Response (schema unchanged)
```

### Logging Enhancements

**Request Start Log:**
```json
{
  "correlation_id": "abc-123-def-456",
  "org_id": "org-financial-001",
  "active_model": "claude-3-5-sonnet",
  "rollback_flag": false,
  "finding_title": "SQL Injection Vulnerability"
}
```

**Request Completion Log:**
```json
{
  "correlation_id": "abc-123-def-456",
  "org_id": "org-financial-001",
  "response_time_ms": 1350.2,
  "model_confidence": 0.75,
  "drift_status": "DRIFT_DETECTED",
  "rollback_flag": false,
  "tokens_used": 5000
}
```

## Use Cases

### 1. SLA Monitoring
- Track response times per request
- Monitor model confidence trends
- Alert on SLA violations
- Generate compliance reports

### 2. Quality Assurance
- Automatic confidence adjustment on drift
- Fallback notices for audit trail
- Transparency in model performance
- Compliance with quality standards

### 3. Emergency Rollback
- Force default model when issues detected
- Override active model selection
- Maintain service availability
- Quick response to incidents

### 4. Compliance Reporting
- Full audit trail with drift notices
- Response time tracking
- Confidence adjustment history
- Model selection transparency

## Safety Features

- **Confidence Floor:** Minimum confidence of 0.1 (never goes below)
- **Non-Breaking:** Response schema unchanged
- **Audit Trail:** All adjustments logged
- **Transparent:** Fallback notices in audit payload
- **Safe Rollback:** Rollback flag overrides all model selection

## Files Modified

1. `app/schemas.py` - Added `rollback_flag` field
2. `app/main.py` - Added:
   - Rollback flag handling
   - Drift-based confidence adjustment
   - Fallback notice generation
   - SLA health reporting fields
   - Enhanced logging

## Compliance Benefits

- **SLA Tracking:** Response time and confidence metrics
- **Quality Assurance:** Automatic confidence adjustment
- **Audit Trail:** Complete drift detection history
- **Emergency Response:** Runtime rollback capability
- **Transparency:** Fallback notices for compliance

