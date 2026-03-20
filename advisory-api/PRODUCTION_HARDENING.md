# Production Hardening and Reliability

## Overview

Enhanced the AI advisory service with production-grade reliability features including multi-model failover, retry with backoff, comprehensive metrics, dynamic model hot-reload, and comprehensive logging.

## Features

### 1. Multi-Model Failover Logic

**Behavior:**
- If `active_model` fails or is unhealthy, automatically falls back to default `MODEL_NAME`
- Failover is transparent to API consumers
- All failover events are logged with `org_id` and `correlation_id`

**Implementation:**
```python
# In advisory_engine.py
try:
    raw_output, token_usage, used_fallback = query_llm(
        prompt=prompt,
        model=model_to_use,
        fallback_model=MODEL_NAME,  # Always fallback to default
        org_id=org_id,
        correlation_id=correlation_id
    )
except Exception:
    # Fallback automatically handled in query_llm
    pass
```

**Logging:**
```json
{
  "level": "WARNING",
  "message": "Model failover occurred",
  "correlation_id": "abc-123-def-456",
  "org_id": "org-financial-001",
  "primary_model": "claude-3-5-sonnet",
  "fallback_model": "mistral:7b-instruct"
}
```

### 2. Request Retry with Exponential Backoff

**Configuration:**
- **Max Retries:** 3 attempts
- **Initial Backoff:** 1.0 seconds
- **Backoff Multiplier:** 2.0x
- **Max Backoff:** 10.0 seconds

**Retry Sequence:**
1. Attempt 1: Immediate
2. Attempt 2: Wait 1.0s
3. Attempt 3: Wait 2.0s
4. Attempt 4: Wait 4.0s (if needed)

**Logging:**
```json
{
  "level": "WARNING",
  "message": "LLM query failed, retrying",
  "correlation_id": "abc-123-def-456",
  "org_id": "org-financial-001",
  "model": "mistral:7b-instruct",
  "attempt": 2,
  "max_retries": 3,
  "wait_time": 1.0
}
```

### 3. Metrics Endpoint

**Endpoint:** `GET /internal/metrics`

**Required Metrics:**
- `requests_total`: Total number of requests
- `failures_total`: Total number of failures
- `degraded_total`: Total number of degraded requests (RAG unavailable)
- `p95_latency`: 95th percentile latency in milliseconds

**Example Response:**
```json
{
  "requests_total": 1250,
  "failures_total": 15,
  "degraded_total": 42,
  "p95_latency": 1850.5,
  "p50_latency_ms": 1250.0,
  "p99_latency_ms": 2100.0,
  "avg_latency_ms": 1350.2,
  "fallback_count": 8,
  "success_count": 1235
}
```

### 4. Dynamic Model Hot-Reload

**Endpoints:**

#### Update Model Configuration
**POST** `/api/v1/ai/governance/model-hot-reload`

**Query Parameters:**
- `model_name`: Model name to set (required)
- `org_id`: Optional organization ID for org-specific model

**Example Request:**
```bash
curl -X POST -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/ai/governance/model-hot-reload?model_name=claude-3-5-sonnet&org_id=org-financial-001"
```

**Example Response:**
```json
{
  "status": "success",
  "message": "Model updated for organization org-financial-001",
  "org_id": "org-financial-001",
  "model_name": "claude-3-5-sonnet"
}
```

#### Get Model Configuration
**GET** `/api/v1/ai/governance/model-config`

**Example Response:**
```json
{
  "default_model": "mistral:7b-instruct",
  "org_model": "claude-3-5-sonnet",
  "org_id": "org-financial-001"
}
```

**Features:**
- **No Restart Required:** Model changes take effect immediately
- **Thread-Safe:** Uses locks for concurrent access
- **Org-Specific:** Supports per-organization model configuration
- **Audit Trail:** All model changes are logged

### 5. Comprehensive Fallback/Failover Logging

**All Events Logged With:**
- `correlation_id`: Request correlation ID
- `org_id`: Organization ID
- `primary_model`: Model that was attempted
- `fallback_model`: Model that was used as fallback
- `error`: Error message (if applicable)

**Log Examples:**

**Failover Event:**
```json
{
  "timestamp": "2026-01-15T10:30:00Z",
  "level": "WARNING",
  "message": "Model failover occurred",
  "correlation_id": "abc-123-def-456",
  "org_id": "org-financial-001",
  "primary_model": "claude-3-5-sonnet",
  "fallback_model": "mistral:7b-instruct"
}
```

**Retry Event:**
```json
{
  "timestamp": "2026-01-15T10:30:01Z",
  "level": "WARNING",
  "message": "LLM query failed, retrying",
  "correlation_id": "abc-123-def-456",
  "org_id": "org-financial-001",
  "model": "mistral:7b-instruct",
  "attempt": 2,
  "max_retries": 3,
  "wait_time": 1.0,
  "error": "Connection timeout"
}
```

## Implementation Details

### Model Selection Priority

1. **Request Payload** (`active_model` field)
2. **Hot-Reload Config** (org-specific from `model_manager`)
3. **Hot-Reload Config** (default from `model_manager`)
4. **Database** (`ai_active_models` table)
5. **Default** (`MODEL_NAME` constant)

### Failover Flow

```
Try Primary Model
    ↓
If Fails:
    - Log warning
    - Try Fallback Model (MODEL_NAME)
    - If Fallback Fails: Raise exception
    ↓
Track in Metrics
    ↓
Log Event
    ↓
Return Response (schema unchanged)
```

### Retry Flow

```
Attempt 1: Immediate
    ↓
If Fails: Wait 1.0s
    ↓
Attempt 2
    ↓
If Fails: Wait 2.0s
    ↓
Attempt 3
    ↓
If Fails: Wait 4.0s
    ↓
Attempt 4 (final)
    ↓
If Fails: Raise exception
```

## Safety Features

- **Non-Breaking:** Response schema unchanged
- **Transparent:** Failover is invisible to API consumers
- **Auditable:** All events logged with correlation IDs
- **Thread-Safe:** Model manager uses locks
- **Graceful:** Retries prevent transient failures
- **Observable:** Comprehensive metrics and logging

## Files Created/Modified

1. `app/ollama_client.py` - Added retry with backoff and failover support
2. `app/advisory_engine.py` - Added failover logic and hot-reload support
3. `app/model_manager.py` - New module for dynamic model management
4. `app/metrics.py` - Enhanced with required metrics
5. `app/main.py` - Updated metrics endpoint and added hot-reload endpoints

## Use Cases

### 1. High Availability
- Automatic failover on model unavailability
- Retry logic for transient failures
- Service continues operating during model issues

### 2. Model Migration
- Hot-reload new models without downtime
- Test models in production
- Roll back quickly if issues detected

### 3. Performance Monitoring
- Track failover frequency
- Monitor retry rates
- Identify model health issues

### 4. Compliance
- Full audit trail of model usage
- Failover event tracking
- Metrics for SLA reporting

## Metrics Tracking

**Fallback Events:**
- `fallback_count`: Total number of failover events
- Tracked per request in metrics
- Included in audit payload

**Retry Events:**
- Logged on each retry attempt
- Includes attempt number and wait time
- Success logged when retry succeeds

## Production Readiness

✅ **Multi-Model Failover:** Automatic fallback to default model  
✅ **Retry with Backoff:** Exponential backoff for transient failures  
✅ **Comprehensive Metrics:** All required metrics exposed  
✅ **Hot-Reload:** Dynamic model configuration without restart  
✅ **Full Logging:** All events logged with correlation IDs  
✅ **Non-Breaking:** Response schema unchanged  

