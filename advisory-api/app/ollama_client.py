import os
import requests
import time
import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434/api/generate")
MODEL_NAME = os.getenv("MODEL_VERSION", "phi3:mini")
FALLBACK_MODEL = None  # No fallback — Phi-3 only

# Demo mode: return mock LLM response without calling Ollama
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

DEMO_RESPONSE = """{
  "risk_summary": "This finding represents a critical security vulnerability that could allow unauthorized access to sensitive system resources. The exposure level is significant based on the nature of the affected component.",
  "business_impact": "Exploitation of this vulnerability could lead to data breaches, service disruption, and potential regulatory non-compliance penalties. Financial and reputational damage are probable outcomes if left unmitigated.",
  "severity": "High",
  "remediation_steps": [
    "Immediately patch the affected component to the latest stable version",
    "Implement network-level access controls to restrict exposure",
    "Enable audit logging on the affected service for forensic readiness",
    "Conduct a full security review of adjacent components",
    "Test remediation in a staging environment before production deployment"
  ],
  "confidence": 0.87
}"""

# Retry configuration
MAX_RETRIES = 1
INITIAL_BACKOFF = 0.5
BACKOFF_MULTIPLIER = 2.0
MAX_BACKOFF = 4.0
REQUEST_TIMEOUT = 60

def query_llm(
    prompt: str,
    model: Optional[str] = None,
    fallback_model: Optional[str] = None,
    org_id: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> Tuple[str, Dict, bool]:
    """
    Query LLM with retry and failover logic.
    In DEMO_MODE, returns mock advisory without calling Ollama.
    """
    if DEMO_MODE:
        logger.info(
            "DEMO_MODE active — returning mock advisory",
            extra={"correlation_id": correlation_id, "org_id": org_id}
        )
        token_usage = {"prompt_eval_count": 256, "eval_count": 128, "total_tokens": 384}
        return DEMO_RESPONSE, token_usage, False

    model_to_use = model or MODEL_NAME
    fallback_to_use = fallback_model if fallback_model is not None else FALLBACK_MODEL
    used_fallback = False

    try:
        response_text, token_usage = _query_llm_with_retry(
            prompt=prompt, model=model_to_use,
            org_id=org_id, correlation_id=correlation_id
        )
        return response_text, token_usage, used_fallback
    except Exception as e:
        if fallback_to_use is None:
            logger.warning(
                "Primary model failed, no fallback configured",
                extra={"correlation_id": correlation_id, "org_id": org_id,
                       "selected_model": model_to_use, "error": str(e)}
            )
            raise
        if fallback_to_use != model_to_use:
            logger.warning(
                "Primary model failed, attempting fallback",
                extra={"correlation_id": correlation_id, "org_id": org_id,
                       "primary_model": model_to_use, "fallback_model": fallback_to_use, "error": str(e)}
            )
            used_fallback = True
            try:
                response_text, token_usage = _query_llm_with_retry(
                    prompt=prompt, model=fallback_to_use,
                    org_id=org_id, correlation_id=correlation_id
                )
                return response_text, token_usage, used_fallback
            except Exception as fallback_error:
                logger.error(
                    "Fallback model also failed",
                    extra={"correlation_id": correlation_id, "org_id": org_id,
                           "primary_model": model_to_use, "fallback_model": fallback_to_use,
                           "error": str(fallback_error)},
                    exc_info=True
                )
                raise fallback_error
        else:
            logger.warning(
                "Primary model failed, no fallback available",
                extra={"correlation_id": correlation_id, "org_id": org_id,
                       "selected_model": model_to_use, "error": str(e)}
            )
            raise

def _query_llm_with_retry(
    prompt: str,
    model: str,
    org_id: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> Tuple[str, Dict]:
    backoff = INITIAL_BACKOFF
    last_exception = None

    for attempt in range(MAX_RETRIES):
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "num_predict": 256,
                    "temperature": 0.2,
                    "num_ctx": 2048
                }
            }
            response = requests.post(OLLAMA_URL, json=payload, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            result = response.json()
            response_text = result.get("response", "")
            prompt_eval_count = result.get("prompt_eval_count") or 0
            eval_count = result.get("eval_count") or 0

            token_usage = {
                "prompt_eval_count": result.get("prompt_eval_count"),
                "eval_count": result.get("eval_count"),
                "total_tokens": prompt_eval_count + eval_count
            }

            if attempt > 0:
                logger.info("LLM query succeeded on retry",
                            extra={"correlation_id": correlation_id, "model": model, "attempt": attempt + 1})

            return response_text, token_usage

        except requests.exceptions.ReadTimeout as e:
            logger.warning("LLM timeout — failing fast",
                           extra={"correlation_id": correlation_id, "model": model, "timeout": REQUEST_TIMEOUT})
            raise
        except Exception as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                wait_time = min(backoff, MAX_BACKOFF)
                logger.warning("LLM query failed, retrying",
                               extra={"correlation_id": correlation_id, "model": model,
                                      "attempt": attempt + 1, "wait_time": wait_time, "error": str(e)})
                time.sleep(wait_time)
                backoff *= BACKOFF_MULTIPLIER
            else:
                logger.warning("LLM query failed after all retries",
                               extra={"correlation_id": correlation_id, "model": model,
                                      "attempts": MAX_RETRIES, "error": str(e)})

    raise last_exception
