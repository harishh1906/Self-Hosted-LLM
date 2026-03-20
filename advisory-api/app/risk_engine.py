from app.risk_mapping import severity_to_score
from app.config import ASSET_CRITICALITY

def calculate_risk_score(
    scanner_severity: str,
    ai_severity: str,
    confidence: float,
    asset: str
) -> dict:

    scanner_score = severity_to_score(scanner_severity)
    ai_score = severity_to_score(ai_severity)
    confidence_score = confidence * 100
    asset_weight = ASSET_CRITICALITY.get(asset, ASSET_CRITICALITY["Default"]) * 100

    final_score = (
        scanner_score * 0.30 +
        ai_score * 0.30 +
        confidence_score * 0.20 +
        asset_weight * 0.20
    )

    risk_score = round(final_score)

    if risk_score >= 85:
        level = "Critical"
        sla = "24h"
    elif risk_score >= 70:
        level = "High"
        sla = "72h"
    elif risk_score >= 40:
        level = "Medium"
        sla = "7d"
    else:
        level = "Low"
        sla = "30d"

    return {
        "risk_score": risk_score,
        "risk_level": level,
        "sla": sla,
        "justification": f"{level} risk based on severity, asset criticality, and AI confidence"
    }
