# Real-Time Model Health Monitoring

## Overview

Real-time model health monitoring system that tracks comprehensive metrics per model without exposing advisory content.

## Features

### 1. Per-Model Metrics Tracking

**Metrics Tracked:**
- **Average Latency:** Rolling average of request latency (milliseconds)
- **SLA Violations:** Count of requests exceeding SLA threshold (2000ms)
- **Fallback Usage:** Count and rate of fallback events
- **Drift Adjustment Rate:** Rate of confidence adjustments due to drift (0.0-1.0)
- **Confidence Trend:** Trend analysis comparing recent vs older confidence averages

**Real-Time Updates:**
- Metrics updated on every request
- Thread-safe tracking with locks
- Rolling window of latency samples (max 1000 per model)
- Automatic calculation of rates and trends

### 2. Model Health Summary Endpoint

**Endpoint:** `GET /internal/control-plane/model-health-summary`

**Response Format:**
```json
{
  "models": [
    {
      "model_name": "mistral:7b-instruct",
      "usage_count": 1250,
      "avg_latency_ms": 1250.5,
      "fallback_count": 2,
      "drift_adjustments": 15,
      "drift_adjustment_rate": 0.012,
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
      "drift_adjustment_rate": 0.009,
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

### 3. Metrics Details

#### Average Latency
- **Calculation:** Rolling average of all latency samples
- **Sample Window:** Last 1000 requests per model
- **Update:** Real-time on each request
- **Unit:** Milliseconds

#### SLA Violations
- **Definition:** Requests with latency > 2000ms (SLA_LATENCY_THRESHOLD)
- **Tracking:** Incremented on each violation
- **Reset:** Never (cumulative count)
- **Use Case:** Identify models with performance issues

#### Fallback Usage
- **Count:** Total number of fallback events
- **Rate:** `fallback_count / usage_count` (0.0-1.0)
- **Tracking:** Incremented when fallback model is used
- **Use Case:** Monitor model reliability

#### Drift Adjustment Rate
- **Count:** Total number of drift adjustments
- **Rate:** `drift_adjustments / usage_count` (0.0-1.0)
- **Tracking:** Incremented when drift is detected and confidence is adjusted
- **Use Case:** Monitor model quality degradation

#### Confidence Trend
- **Recent Average:** Average confidence from last 10 requests
- **Older Average:** Average confidence from previous 10 requests
- **Drop Percent:** Percentage change in confidence
- **Is Declining:** True if drop > 10%
- **Sample Count:** Total confidence samples tracked (max 100 per model)

### 4. Privacy and Security

**No Advisory Content Exposed:**
- Endpoint returns only metrics and statistics
- No finding descriptions
- No advisory text
- No risk assessments
- No remediation steps
- Only aggregated performance data

**Data Included:**
- Model identifiers
- Performance metrics
- Usage statistics
- Trend analysis
- No sensitive content

## Implementation Details

### Model Health Tracker

**Thread-Safe Tracking:**
```python
class ModelHealthTracker:
    - Uses locks for thread safety
    - Per-model metrics dictionary
    - Rolling latency samples (deque, max 1000)
    - Real-time metric updates
```

**Metrics Recorded:**
- Latency samples (rolling window)
- Fallback count (incremental)
- Drift adjustment count (incremental)
- SLA violation count (incremental)
- Total requests (incremental)
- Last used timestamp (updated on each request)

### Confidence Trend Analysis

**Performance Intelligence:**
- Maintains rolling history (last 100 values per model)
- Compares recent window (last 10) vs older window (previous 10)
- Calculates drop percentage
- Flags declining trends (> 10% drop)

**Trend Calculation:**
```python
recent_avg = mean(last 10 confidence values)
older_avg = mean(previous 10 confidence values)
drop_percent = ((older_avg - recent_avg) / older_avg) * 100
is_declining = drop_percent > 10%
```

### Real-Time Updates

**Update Flow:**
```
Request → Record Metrics
    ↓
Update:
- Latency sample
- Total requests
- Last used timestamp
- Fallback count (if used)
- Drift adjustment count (if adjusted)
- SLA violation count (if violated)
    ↓
Calculate:
- Average latency
- Fallback rate
- Drift adjustment rate
    ↓
Available via endpoint
```

## Use Cases

### 1. Performance Monitoring
- Track model latency trends
- Identify slow models
- Monitor SLA compliance
- Capacity planning

### 2. Quality Assurance
- Monitor drift frequency
- Track confidence trends
- Identify quality degradation
- Trigger alerts on decline

### 3. Reliability Monitoring
- Track fallback frequency
- Identify unreliable models
- Monitor model health
- Support model selection decisions

### 4. Control Plane Operations
- Real-time health dashboards
- Model performance comparison
- SLA violation alerts
- Trend analysis

## Safety Features

- **No Content Exposure:** Only metrics, no advisory content
- **Thread-Safe:** All operations use locks
- **Real-Time:** Metrics updated immediately
- **Efficient:** Rolling window limits memory usage
- **Scalable:** Per-model tracking supports multiple models

## Configuration

### SLA Threshold
```python
SLA_LATENCY_THRESHOLD = 2000.0  # 2 seconds
```

### Sample Window
```python
max_samples = 1000  # Per model
```

### Confidence History
```python
max_history = 100  # Per model
```

## Files

1. `app/model_health.py` - Model health tracker with real-time metrics
2. `app/model_health_summary.py` - Control plane health summary generator
3. `app/performance_intelligence.py` - Confidence trend analysis
4. `app/main.py` - Endpoint implementation

## Production Readiness

✅ **Real-Time Tracking:** Metrics updated on every request  
✅ **Comprehensive Metrics:** All required fields tracked  
✅ **Privacy Safe:** No advisory content exposed  
✅ **Thread-Safe:** Concurrent request handling  
✅ **Efficient:** Rolling windows limit memory usage  

