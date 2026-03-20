# Production Monitoring Mode

## Overview

Enhanced the AI advisory service with production monitoring capabilities including real-time model health tracking, load-aware degradation, and cluster-wide consistency for model hot-reload.

## Features

### 1. Real-Time Model Health Metrics

**Per-Model Tracking:**
- Request latency (average)
- Model fallback frequency
- Advisory confidence changes due to drift
- Model load status (recent usage)

**Metrics Collected:**
- `avg_latency_ms`: Average request latency per model
- `fallback_count`: Number of fallback events
- `drift_adjustment_rate`: Rate of confidence adjustments (0.0-1.0)
- `is_loaded`: Whether model has been used in the last hour
- `total_requests`: Total requests processed by model

### 2. Model Health Endpoint

**Endpoint:** `GET /internal/model-health`

**Response Format:**
```json
{
  "models": [
    {
      "model_name": "mistral:7b-instruct",
      "is_loaded": true,
      "avg_latency_ms": 1250.5,
      "fallback_count": 2,
      "drift_adjustment_rate": 0.05
    },
    {
      "model_name": "claude-3-5-sonnet",
      "is_loaded": true,
      "avg_latency_ms": 1850.2,
      "fallback_count": 0,
      "drift_adjustment_rate": 0.02
    }
  ]
}
```

### 3. Load-Aware Advisory Degradation

**Behavior:**
- When model latency exceeds SLA threshold (2000ms), automatically reduces verbosity
- Degradation path: `detailed` → `balanced` → `concise`
- Preserves advisory response schema (non-breaking)

**SLA Configuration:**
- Threshold: 2000ms (configurable via `SLA_LATENCY_THRESHOLD_MS`)
- Applied per-model based on average latency

**Example:**
```
Model: claude-3-5-sonnet
Avg Latency: 2150ms (> 2000ms SLA)
Original Verbosity: detailed
Degraded Verbosity: balanced
```

**Logging:**
```json
{
  "level": "INFO",
  "message": "Load-aware verbosity degradation",
  "correlation_id": "abc-123-def-456",
  "org_id": "org-financial-001",
  "model_name": "claude-3-5-sonnet",
  "original_verbosity": "detailed",
  "degraded_verbosity": "balanced",
  "avg_latency_ms": 2150.5,
  "sla_threshold_ms": 2000.0
}
```

### 4. Cluster-Wide Model Hot-Reload Consistency

**Database-Backed Configuration:**
- Model configurations stored in `model_configurations` table
- All cluster instances read from shared database
- Cache with 60-second TTL for performance

**Table Schema:**
```sql
CREATE TABLE model_configurations (
    id SERIAL PRIMARY KEY,
    config_key VARCHAR UNIQUE NOT NULL,  -- "default" or "org:{org_id}"
    model_name VARCHAR NOT NULL,
    enabled VARCHAR NOT NULL DEFAULT 'true',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by VARCHAR,
    correlation_id VARCHAR
);
```

**Consistency Guarantees:**
- Updates persisted to database immediately
- All instances refresh cache every 60 seconds
- Cache invalidation on updates
- Correlation ID tracking for audit trail

**Example Update:**
```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "X-Request-ID: update-123" \
  "http://localhost:8000/api/v1/ai/governance/model-hot-reload?model_name=claude-3-5-sonnet"
```

**Response:**
```json
{
  "status": "success",
  "message": "Default model updated (cluster-wide)",
  "model_name": "claude-3-5-sonnet",
  "correlation_id": "update-123"
}
```

## Implementation Details

### Model Health Tracking

**Tracking Flow:**
```
Request → LLM Call → Record Metrics
    ↓
Track:
- Model name (actual model used, including fallback)
- Latency (LLM call time)
- Fallback flag
- Drift adjustment flag
    ↓
Update ModelHealthTracker
```

**ModelHealthTracker:**
- Thread-safe metrics collection
- Per-model latency samples (deque, max 1000 samples)
- Automatic calculation of averages and rates
- Tracks model load status (used in last hour)

### Load-Aware Degradation

**Degradation Logic:**
```python
if model_health["avg_latency_ms"] > SLA_LATENCY_THRESHOLD_MS:
    if original_verbosity == "detailed":
        degraded_verbosity = "balanced"
    elif original_verbosity == "balanced":
        degraded_verbosity = "concise"
    # concise stays concise
```

**Integration:**
- Applied before prompt shaping
- Policy verbosity updated temporarily
- Original policy preserved (not modified in database)
- Logged for observability

### Cluster-Wide Consistency

**Model Manager Architecture:**
```
In-Memory Cache (60s TTL)
    ↓
Database (Source of Truth)
    ↓
All Cluster Instances
```

**Update Flow:**
```
1. Update in-memory cache
2. Persist to database
3. Invalidate cache on other instances (via TTL)
4. Log update with correlation_id
```

**Cache Strategy:**
- 60-second TTL for performance
- Automatic refresh on cache miss
- Cache invalidation on updates
- Thread-safe operations

## Monitoring Use Cases

### 1. Model Performance Monitoring
- Track latency trends per model
- Identify slow models
- Monitor fallback frequency
- Detect model health issues

### 2. Load Management
- Automatic verbosity reduction under load
- Maintain SLA compliance
- Preserve service availability
- Reduce latency during high load

### 3. Cluster Coordination
- Consistent model configuration across instances
- Zero-downtime model updates
- Audit trail for all changes
- Multi-instance deployment support

### 4. Drift Detection
- Track confidence adjustment rate
- Monitor model quality degradation
- Identify models with frequent drift
- Correlate drift with latency

## Configuration

### SLA Threshold
```python
# app/config.py
SLA_LATENCY_THRESHOLD_MS = 2000.0  # 2 seconds
```

### Cache TTL
```python
# app/model_manager.py
self._cache_ttl = 60  # 60 seconds
```

### Model Load Window
```python
# app/model_health.py
is_loaded = (datetime.utcnow() - last_used).total_seconds() < 3600  # 1 hour
```

## Safety Features

- **Non-Breaking:** Response schema unchanged
- **Transparent:** Degradation logged for observability
- **Consistent:** Cluster-wide model configuration
- **Auditable:** All updates tracked with correlation IDs
- **Resilient:** Graceful degradation under load
- **Thread-Safe:** All operations use locks

## Files Created/Modified

1. `app/model_health.py` - New module for model health tracking
2. `app/model_manager.py` - Enhanced with cluster-wide consistency
3. `app/advisory_engine.py` - Added load-aware verbosity degradation
4. `app/main.py` - Added model health tracking and endpoint
5. `app/config.py` - Added SLA threshold configuration
6. `app/db/models.py` - Added ModelConfiguration table

## Database Migration

**New Table:** `model_configurations`

```sql
CREATE TABLE model_configurations (
    id SERIAL PRIMARY KEY,
    config_key VARCHAR UNIQUE NOT NULL,
    model_name VARCHAR NOT NULL,
    enabled VARCHAR NOT NULL DEFAULT 'true',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by VARCHAR,
    correlation_id VARCHAR
);

CREATE INDEX idx_model_config_key ON model_configurations(config_key);
```

## Production Readiness

✅ **Real-Time Metrics:** Per-model health tracking  
✅ **Load-Aware Degradation:** Automatic verbosity reduction  
✅ **Cluster Consistency:** Database-backed configuration  
✅ **Monitoring Endpoint:** `/internal/model-health`  
✅ **Audit Trail:** Correlation ID tracking  
✅ **Non-Breaking:** Response schema unchanged  

