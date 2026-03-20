"""
Prompt Shaping Based on AI Policy Profiles
Modifies system prompt based on tenant policy while preserving output schema.
"""
from typing import Dict

def shape_prompt(base_prompt: str, policy: Dict) -> str:
    """
    Shape the advisory prompt based on AI policy profile.
    
    Modifies only the system instructions, never the output format.
    Preserves exact output schema requirements.
    
    Args:
        base_prompt: Base advisory prompt template
        policy: Policy profile dict with risk_tolerance, verbosity, compliance_mode, remediation_style
    
    Returns:
        Shaped prompt with policy-specific instructions
    """
    # Extract policy settings
    risk_tolerance = policy.get("risk_tolerance", "medium")
    verbosity = policy.get("verbosity", "balanced")
    compliance_mode = policy.get("compliance_mode", "none")
    remediation_style = policy.get("remediation_style", "practical")
    
    # Build policy-specific instructions (inserted before output format)
    policy_instructions = []
    
    # Risk tolerance guidance
    if risk_tolerance == "low":
        policy_instructions.append("Emphasize conservative risk assessment. Prioritize security over convenience.")
    elif risk_tolerance == "high":
        policy_instructions.append("Focus on practical risk assessment. Balance security with operational needs.")
    # medium: no specific instruction (default behavior)
    
    # Verbosity guidance
    if verbosity == "concise":
        policy_instructions.append("Keep explanations brief and to the point. Focus on essential information only.")
    elif verbosity == "detailed":
        policy_instructions.append("Provide comprehensive explanations. Include context and background where helpful.")
    # balanced: no specific instruction (default behavior)
    
    # Compliance mode guidance
    if compliance_mode == "soc2":
        policy_instructions.append("Align recommendations with SOC 2 controls. Emphasize access controls and monitoring.")
    elif compliance_mode == "iso":
        policy_instructions.append("Align recommendations with ISO 27001 standards. Emphasize risk management and controls.")
    elif compliance_mode == "hipaa":
        policy_instructions.append("Align recommendations with HIPAA requirements. Emphasize data protection and privacy controls.")
    # none: no specific instruction
    
    # Remediation style guidance
    if remediation_style == "strict":
        policy_instructions.append("Provide strict, immediate remediation steps. Prioritize security fixes over operational continuity.")
    elif remediation_style == "educational":
        policy_instructions.append("Include educational context in remediation steps. Explain why each step is important.")
    # practical: no specific instruction (default behavior)
    
    # Insert policy instructions into prompt (after initial instructions, before output format)
    if policy_instructions:
        policy_section = "\n\nPOLICY GUIDANCE:\n" + "\n".join(f"- {inst}" for inst in policy_instructions)
        
        # Insert before "---START---" section
        if "---START---" in base_prompt:
            base_prompt = base_prompt.replace("---START---", policy_section + "\n\n---START---")
        else:
            # Fallback: append before output format section
            base_prompt = base_prompt + "\n\n" + policy_section
    
    return base_prompt

