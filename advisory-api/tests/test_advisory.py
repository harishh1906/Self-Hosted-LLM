"""
Full test suite for VirtueThreatX Advisory API.

Covers:
- Schema validation
- Health endpoints
- Auth (JWT + HMAC)
- /analyze endpoint (demo mode)
- Policy CRUD
- Risk engine
- Drift detection logic
- Circuit breaker
"""

import os
import sys
import json
import pytest
import time

# Set DEMO_MODE and required env vars BEFORE importing app modules
os.environ["DEMO_MODE"] = "true"
os.environ["SERVICE_SECRET_KEY"] = "test-secret-key-for-unit-tests-32chars"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-unit-tests-32"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["QDRANT_HOST"] = "localhost"

from fastapi.testclient import TestClient
from app.main import app
from app.schemas import FindingInput, PolicyProfileUpdate, AdvisoryStructuredResponse
from app.auth.jwt import create_access_token, decode_access_token
from app.risk_engine import calculate_risk_score
from app.circuit_breaker import CircuitBreaker

# ─── Test Client ────────────────────────────────────────────
client = TestClient(app)


# ─── Helpers ────────────────────────────────────────────────
def get_auth_token(username: str = "testuser", role: str = "security_analyst", org_id: str = "test-org"):
    """Generate a valid JWT token for testing."""
    return create_access_token({"sub": username, "role": role, "org_id": org_id})


def auth_headers(org_id: str = "test-org"):
    return {"Authorization": f"Bearer {get_auth_token(org_id=org_id)}"}


SAMPLE_FINDING = {
    "title": "SQL Injection in login endpoint",
    "description": "The login endpoint is vulnerable to SQL injection. User-supplied input is concatenated directly into the SQL query without sanitization.",
    "severity": "Critical",
    "evidence": "' OR 1=1-- was accepted as a valid username.",
    "affected_asset": "Authentication Service",
    "scanner": "burp_suite",
    "org_id": "test-org"
}


# ═══════════════════════════════════════════════════════════════
# SECTION 1: Schema Validation
# ═══════════════════════════════════════════════════════════════

class TestSchemaValidation:
    """Test Pydantic schema validation rules."""

    def test_finding_input_valid(self):
        finding = FindingInput(**SAMPLE_FINDING)
        assert finding.title == "SQL Injection in login endpoint"
        assert finding.severity == "Critical"
        assert finding.org_id == "test-org"

    def test_finding_input_empty_title_fails(self):
        with pytest.raises(Exception):
            FindingInput(title="", description="test desc", org_id="org1")

    def test_finding_input_title_too_long_fails(self):
        with pytest.raises(Exception):
            FindingInput(title="x" * 501, description="test", org_id="org1")

    def test_finding_input_invalid_severity_fails(self):
        with pytest.raises(Exception):
            FindingInput(
                title="Test",
                description="test desc",
                severity="EXTREME",  # invalid
                org_id="org1"
            )

    def test_finding_input_valid_severities(self):
        for sev in ["Low", "Medium", "High", "Critical"]:
            f = FindingInput(title="Test", description="desc", severity=sev, org_id="org1")
            assert f.severity == sev

    def test_finding_input_invalid_org_id_chars(self):
        with pytest.raises(Exception):
            FindingInput(title="Test", description="desc", org_id="org id with spaces!")

    def test_finding_input_invalid_risk_tolerance(self):
        with pytest.raises(Exception):
            FindingInput(title="Test", description="desc", org_id="org1", risk_tolerance="extreme")

    def test_finding_input_valid_risk_tolerance(self):
        for rt in ["low", "medium", "high"]:
            f = FindingInput(title="Test", description="desc", org_id="org1", risk_tolerance=rt)
            assert f.risk_tolerance == rt

    def test_finding_input_invalid_verbosity(self):
        with pytest.raises(Exception):
            FindingInput(title="Test", description="desc", org_id="org1", verbosity="verbose")

    def test_policy_profile_update_valid(self):
        p = PolicyProfileUpdate(
            org_id="org1",
            risk_tolerance="high",
            verbosity="detailed",
            compliance_mode="soc2",
            remediation_style="strict"
        )
        assert p.org_id == "org1"
        assert p.compliance_mode == "soc2"

    def test_policy_profile_update_invalid_compliance(self):
        with pytest.raises(Exception):
            PolicyProfileUpdate(compliance_mode="gdpr")  # not in allowed list

    def test_advisory_structured_response_valid(self):
        advisory = AdvisoryStructuredResponse(
            risk_summary="High risk finding",
            business_impact="Data breach possible",
            severity="High",
            remediation_steps=["Step 1", "Step 2"],
            confidence=0.87
        )
        assert advisory.confidence == 0.87
        assert len(advisory.remediation_steps) == 2


# ═══════════════════════════════════════════════════════════════
# SECTION 2: Health Endpoints
# ═══════════════════════════════════════════════════════════════

class TestHealthEndpoints:
    """Test health and readiness endpoints."""

    def test_health_check_returns_ok(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "demo_mode" in data

    def test_health_check_demo_mode_true(self):
        response = client.get("/health")
        data = response.json()
        # We set DEMO_MODE=true in env
        assert data["demo_mode"] is True

    def test_docs_endpoint_available(self):
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_json_available(self):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema["info"]["title"] == "VirtueThreatX Advisory API"


# ═══════════════════════════════════════════════════════════════
# SECTION 3: Authentication
# ═══════════════════════════════════════════════════════════════

class TestAuthentication:
    """Test JWT creation, decoding, and auth middleware."""

    def test_create_and_decode_jwt(self):
        token = create_access_token({"sub": "user1", "role": "admin", "org_id": "org1"})
        payload = decode_access_token(token)
        assert payload["sub"] == "user1"
        assert payload["role"] == "admin"
        assert payload["org_id"] == "org1"

    def test_decode_invalid_token_raises(self):
        with pytest.raises(ValueError):
            decode_access_token("this.is.not.a.valid.token")

    def test_login_endpoint_returns_token(self):
        response = client.post("/login?username=testuser&role=security_analyst&org_id=test-org")
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_analyze_requires_auth(self):
        """Ensure /analyze returns 401 without auth header."""
        response = client.post("/analyze", json=SAMPLE_FINDING)
        assert response.status_code == 401

    def test_analyze_accepts_valid_jwt(self):
        """Ensure /analyze works with a valid JWT (demo mode)."""
        response = client.post(
            "/analyze",
            json=SAMPLE_FINDING,
            headers=auth_headers()
        )
        assert response.status_code == 200

    def test_analyze_rejects_bad_token(self):
        """Ensure /analyze rejects invalid JWT."""
        response = client.post(
            "/analyze",
            json=SAMPLE_FINDING,
            headers={"Authorization": "Bearer bad.token.value"}
        )
        assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════
# SECTION 4: Advisory Endpoint (Demo Mode)
# ═══════════════════════════════════════════════════════════════

class TestAdvisoryEndpoint:
    """Test the /analyze endpoint in demo mode."""

    def test_analyze_returns_advisory(self):
        response = client.post(
            "/analyze",
            json=SAMPLE_FINDING,
            headers=auth_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert "advisory" in data
        assert "risk_assessment" in data
        assert "finding" in data

    def test_analyze_advisory_has_required_fields(self):
        response = client.post(
            "/analyze",
            json=SAMPLE_FINDING,
            headers=auth_headers()
        )
        advisory = response.json()["advisory"]
        assert "risk_summary" in advisory
        assert "business_impact" in advisory
        assert "severity" in advisory
        assert "remediation_steps" in advisory
        assert "confidence" in advisory

    def test_analyze_risk_assessment_has_required_fields(self):
        response = client.post(
            "/analyze",
            json=SAMPLE_FINDING,
            headers=auth_headers()
        )
        risk = response.json()["risk_assessment"]
        assert "risk_score" in risk
        assert "risk_level" in risk
        assert "sla" in risk

    def test_analyze_severity_valid(self):
        response = client.post(
            "/analyze",
            json=SAMPLE_FINDING,
            headers=auth_headers()
        )
        severity = response.json()["advisory"]["severity"]
        assert severity in ["Low", "Medium", "High", "Critical"]

    def test_analyze_confidence_in_range(self):
        response = client.post(
            "/analyze",
            json=SAMPLE_FINDING,
            headers=auth_headers()
        )
        confidence = response.json()["advisory"]["confidence"]
        assert 0.0 <= confidence <= 1.0

    def test_analyze_org_id_mismatch_returns_400(self):
        """org_id in finding must match org_id in JWT token."""
        finding = {**SAMPLE_FINDING, "org_id": "different-org"}
        response = client.post(
            "/analyze",
            json=finding,
            headers=auth_headers(org_id="test-org")  # different from finding
        )
        assert response.status_code == 400

    def test_analyze_missing_org_id_returns_400(self):
        """org_id is required for multi-tenant isolation."""
        finding = {k: v for k, v in SAMPLE_FINDING.items() if k != "org_id"}
        response = client.post(
            "/analyze",
            json=finding,
            headers={"Authorization": f"Bearer {create_access_token({'sub': 'user', 'role': 'analyst'})}"}
        )
        assert response.status_code == 400

    def test_demo_analyze_no_auth_required(self):
        """Demo endpoint works without authentication."""
        response = client.post("/demo/analyze")
        assert response.status_code == 200
        data = response.json()
        assert data["demo_mode"] is True
        assert "advisory" in data
        assert "risk_assessment" in data

    def test_analyze_with_rollback_flag(self):
        """rollback_flag=true forces use of default model."""
        finding = {**SAMPLE_FINDING, "rollback_flag": True}
        response = client.post(
            "/analyze",
            json=finding,
            headers=auth_headers()
        )
        assert response.status_code == 200

    def test_analyze_with_policy_overrides(self):
        """Scanner can override policy params per-request."""
        finding = {
            **SAMPLE_FINDING,
            "risk_tolerance": "high",
            "verbosity": "concise",
            "remediation_style": "strict"
        }
        response = client.post(
            "/analyze",
            json=finding,
            headers=auth_headers()
        )
        assert response.status_code == 200

    def test_analyze_remediation_steps_is_list(self):
        response = client.post(
            "/analyze",
            json=SAMPLE_FINDING,
            headers=auth_headers()
        )
        steps = response.json()["advisory"]["remediation_steps"]
        assert isinstance(steps, list)
        assert len(steps) > 0


# ═══════════════════════════════════════════════════════════════
# SECTION 5: Risk Engine
# ═══════════════════════════════════════════════════════════════

class TestRiskEngine:
    """Test the deterministic risk scoring engine."""

    def test_critical_severity_high_score(self):
        result = calculate_risk_score(
            scanner_severity="Critical",
            ai_severity="Critical",
            confidence=0.95,
            asset="Authentication Service"
        )
        assert result["risk_score"] >= 80
        assert result["risk_level"] in ["Critical", "High"]

    def test_low_severity_low_score(self):
        result = calculate_risk_score(
            scanner_severity="Low",
            ai_severity="Low",
            confidence=0.5,
            asset="Default"
        )
        assert result["risk_score"] <= 50

    def test_risk_score_in_valid_range(self):
        result = calculate_risk_score(
            scanner_severity="Medium",
            ai_severity="Medium",
            confidence=0.75,
            asset="Internal API"
        )
        assert 0 <= result["risk_score"] <= 100

    def test_risk_result_has_sla(self):
        result = calculate_risk_score(
            scanner_severity="High",
            ai_severity="High",
            confidence=0.85,
            asset="Customer Database"
        )
        assert "sla" in result
        assert result["sla"]  # non-empty

    def test_risk_result_has_justification(self):
        result = calculate_risk_score(
            scanner_severity="Medium",
            ai_severity="High",
            confidence=0.80,
            asset="Default"
        )
        assert "justification" in result
        assert isinstance(result["justification"], str)

    def test_high_criticality_asset_raises_score(self):
        result_critical_asset = calculate_risk_score(
            scanner_severity="Medium",
            ai_severity="Medium",
            confidence=0.75,
            asset="Authentication Service"  # criticality 1.0
        )
        result_low_asset = calculate_risk_score(
            scanner_severity="Medium",
            ai_severity="Medium",
            confidence=0.75,
            asset="Default"  # criticality 0.5
        )
        assert result_critical_asset["risk_score"] >= result_low_asset["risk_score"]


# ═══════════════════════════════════════════════════════════════
# SECTION 6: Circuit Breaker
# ═══════════════════════════════════════════════════════════════

class TestCircuitBreaker:
    """Test circuit breaker state machine."""

    def test_circuit_breaker_starts_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=5)
        state = cb.get_state()
        assert state["state"] == "closed"

    def test_circuit_opens_after_failure_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=5)
        for _ in range(3):
            cb.record_request(success=False, failed=True)
        state = cb.get_state()
        assert state["state"] == "open"

    def test_circuit_records_success(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=5)
        cb.record_request(success=True, failed=False)
        state = cb.get_state()
        assert state["state"] == "closed"
        assert state["failure_count"] == 0

    def test_circuit_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        cb.record_request(success=False, failed=True)
        time.sleep(1.1)
        state = cb.get_state()
        assert state["state"] in ["half_open", "closed"]


# ═══════════════════════════════════════════════════════════════
# SECTION 7: Metrics Endpoint
# ═══════════════════════════════════════════════════════════════

class TestMetricsEndpoints:
    """Test internal metrics and health endpoints."""

    def test_internal_health_returns_status(self):
        response = client.get("/internal/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data or "circuit_breaker" in data

    def test_internal_metrics_returns_counters(self):
        response = client.get("/internal/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "requests_total" in data
        assert "failures_total" in data
        assert "p95_latency" in data

    def test_internal_metrics_numeric_values(self):
        response = client.get("/internal/metrics")
        data = response.json()
        assert isinstance(data["requests_total"], (int, float))
        assert isinstance(data["p95_latency"], (int, float))


# ═══════════════════════════════════════════════════════════════
# SECTION 8: Policy Endpoints  (require JWT)
# ═══════════════════════════════════════════════════════════════

class TestPolicyEndpoints:
    """Test policy management CRUD endpoints."""

    def test_get_policy_returns_default_if_none(self):
        response = client.get(
            "/api/v1/ai/governance/policy/brand-new-org",
            headers=auth_headers(org_id="brand-new-org")
        )
        assert response.status_code == 200
        data = response.json()
        assert data["org_id"] == "brand-new-org"
        assert data["source"] == "default"

    def test_create_policy_success(self):
        response = client.post(
            "/api/v1/ai/governance/policy",
            json={
                "org_id": "test-org",
                "risk_tolerance": "high",
                "verbosity": "detailed",
                "compliance_mode": "soc2",
                "remediation_style": "strict"
            },
            headers=auth_headers(org_id="test-org")
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["risk_tolerance"] == "high"
        assert data["compliance_mode"] == "soc2"

    def test_create_policy_wrong_org_forbidden(self):
        """Cannot create policy for a different org."""
        response = client.post(
            "/api/v1/ai/governance/policy",
            json={
                "org_id": "other-org",
                "risk_tolerance": "low"
            },
            headers=auth_headers(org_id="test-org")  # different org
        )
        assert response.status_code == 403

    def test_get_policy_after_create(self):
        # Create first
        client.post(
            "/api/v1/ai/governance/policy",
            json={"org_id": "policy-test-org", "verbosity": "concise"},
            headers=auth_headers(org_id="policy-test-org")
        )
        # Then get
        response = client.get(
            "/api/v1/ai/governance/policy/policy-test-org",
            headers=auth_headers(org_id="policy-test-org")
        )
        assert response.status_code == 200
        data = response.json()
        assert data["verbosity"] == "concise"


# ═══════════════════════════════════════════════════════════════
# Run tests
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
