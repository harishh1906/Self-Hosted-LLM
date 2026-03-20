SEVERITY_MAP = {
    "Low": 25,
    "Medium": 50,
    "High": 75,
    "Critical": 100
}

def severity_to_score(severity: str) -> int:
    return SEVERITY_MAP.get(severity, 50)
