# Endpoint Fixes and Schema Alignment

## Summary
Fixed hanging internal endpoints and aligned analytics + audit schemas for production reliability.

## Changes Made

### 1. Added `model_name` Column to `ai_cost_analytics`
- Added `model_name VARCHAR` column to track which model was used for each request
- Updated `record_analytics()` function to accept and store `model_name`
- Updated all `record_analytics()` calls in `main.py` to pass `model_name`

### 2. Fixed `/internal/model-health` Endpoint
- **Before**: Used in-memory `model_health_tracker` which could hang
- **After**: Queries `ai_cost_analytics` directly for fast aggregation
- Returns per-model metrics:
  - `model_name`: Model identifier
  - `usage_count`: Total requests
  - `avg_latency_ms`: Average latency
  - `tokens_used_total`: Total tokens
  - `fallback_count`: From audit logs (30 days)
  - `drift_adjustments`: From audit logs (30 days)
  - `sla_violations`: Count of requests with latency > 2000ms
  - `last_used_at`: ISO timestamp
- Added graceful error handling - returns empty list on failure

### 3. Fixed `/internal/optimization-insights` Endpoint
- **Before**: Could hang on slow JSONB queries
- **After**: 
  - Uses `ai_cost_analytics` for model performance (fast)
  - Queries audit logs with error handling (graceful degradation)
  - Returns empty structure on any error instead of hanging
- Returns:
  - `top_performing_models`: Ranked by latency + success rate
  - `fallback_usage_stats`: Overall fallback statistics
  - `drift_adjustment_trends`: 30-day grouped counts
  - `policy_profile_effectiveness`: Avg confidence + latency per policy_id
  - `model_selection_decision_chains`: Last 100 requests

### 4. Updated Audit Log Payload
- Added `model_name_used`: For easy querying
- Added `confidence`: Alias for `model_confidence`
- Added `endpoint`: "analyze" for querying
- Added `latency_ms`: For querying
- Ensured `risk_score`, `confidence`, `drift_status` are always present

### 5. Added Database Indexes
Created migration script: `advisory-api/migrations/add_indexes.sql`

Indexes added:
- `idx_ai_cost_analytics_model_name`: On `ai_cost_analytics.model_name`
- `idx_ai_cost_analytics_org_model`: Composite on `(org_id, model_name, created_at)`
- `idx_audit_logs_model_name_used`: GIN index on `payload->'model_name_used'`
- `idx_audit_logs_actual_model_used`: GIN index on `payload->'actual_model_used'`
- `idx_audit_logs_drift_status`: GIN index on `payload->'drift_status'`
- `idx_audit_logs_model_selection`: GIN index on `payload->'model_selection'`

### 6. Graceful Error Handling
- All endpoints return empty JSON structures on errors instead of hanging
- Database errors are caught and logged, but don't block responses
- JSONB queries have try/except blocks for graceful degradation

## Database Migration Required

Run these commands to add the `model_name` column and indexes:

```bash
# Add model_name column
docker exec -it virtue-postgres psql -U virtue -d virtue -c "ALTER TABLE ai_cost_analytics ADD COLUMN IF NOT EXISTS model_name VARCHAR;"

# Add indexes
docker exec -it virtue-postgres psql -U virtue -d virtue -c "CREATE INDEX IF NOT EXISTS idx_ai_cost_analytics_model_name ON ai_cost_analytics(model_name);"
docker exec -it virtue-postgres psql -U virtue -d virtue -c "CREATE INDEX IF NOT EXISTS idx_ai_cost_analytics_org_model ON ai_cost_analytics(org_id, model_name, created_at);"
docker exec -it virtue-postgres psql -U virtue -d virtue -c "CREATE INDEX IF NOT EXISTS idx_audit_logs_model_name_used ON audit_logs USING GIN ((payload->'model_name_used'));"
docker exec -it virtue-postgres psql -U virtue -d virtue -c "CREATE INDEX IF NOT EXISTS idx_audit_logs_actual_model_used ON audit_logs USING GIN ((payload->'actual_model_used'));"
docker exec -it virtue-postgres psql -U virtue -d virtue -c "CREATE INDEX IF NOT EXISTS idx_audit_logs_drift_status ON audit_logs USING GIN ((payload->'drift_status'));"
docker exec -it virtue-postgres psql -U virtue -d virtue -c "CREATE INDEX IF NOT EXISTS idx_audit_logs_model_selection ON audit_logs USING GIN ((payload->'model_selection'));"
```

Or use the migration file:
```bash
docker exec -i virtue-postgres psql -U virtue -d virtue < advisory-api/migrations/add_indexes.sql
```

## Testing

After migration, test the endpoints:

```bash
# Test model health (should return quickly)
curl http://localhost:8000/internal/model-health

# Test optimization insights (should return quickly)
curl http://localhost:8000/internal/optimization-insights

# Test policy effectiveness
curl http://localhost:8000/internal/policy-effectiveness
```

## Backward Compatibility

- All changes are backward compatible
- Existing advisory response schema unchanged
- New fields in audit logs are optional (won't break existing queries)
- Endpoints return empty structures on errors (no crashes)

