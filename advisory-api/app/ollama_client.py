import requests
import time
import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://ollama:11434/api/generate"
MODEL_NAME = "phi3:mini"
FALLBACK_MODEL = None  # No fallback - Phi-3 only (prevents cascade failures and RAM explosion)

# Retry configuration (Production-safe: fail fast, no retry storms)
MAX_RETRIES = 1  # No retry storm - Phi-3 responds in <10s normally
INITIAL_BACKOFF = 0.5  # seconds
BACKOFF_MULTIPLIER = 2.0
MAX_BACKOFF = 4.0  # seconds
REQUEST_TIMEOUT = 12  # Phi-3 responds in <10s normally

def query_llm(
    prompt: str,
    model: Optional[str] = None,
    fallback_model: Optional[str] = None,
    org_id: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> Tuple[str, Dict, bool]:
    """
    Query LLM with retry and failover logic.
    
    Args:
        prompt: The prompt to send to the LLM
        model: Optional model name to use (defaults to MODEL_NAME)
        fallback_model: Fallback model to use if primary fails
        org_id: Organization ID for logging
        correlation_id: Correlation ID for logging
    
    Returns:
        tuple: (response_text, token_usage_dict, used_fallback)
        - response_text: The LLM response
        - token_usage_dict: Contains 'prompt_eval_count', 'eval_count', 'total_tokens' if available
        - used_fallback: True if fallback model was used
    """
    # Use provided model or fall back to default (phi3:mini)
    model_to_use = model or MODEL_NAME
    # Fallback disabled - Phi-3 only (no cascade failures)
    fallback_to_use = fallback_model if fallback_model is not None else FALLBACK_MODEL
    used_fallback = False
    
    # Try primary model first
    try:
        response_text, token_usage = _query_llm_with_retry(
            prompt=prompt,
            model=model_to_use,
            org_id=org_id,
            correlation_id=correlation_id
        )
        return response_text, token_usage, used_fallback
    except Exception as e:
        # If no fallback available, fail fast with clean error
        if fallback_to_use is None:
            logger.warning(
                f"Primary model failed after all retries, no fallback configured",
                extra={
                    "correlation_id": correlation_id,
                    "org_id": org_id,
                    "selected_model": model_to_use,
                    "primary_model": model_to_use,
                    "actual_model_used": None,
                    "error": str(e),
                    "decision_reason": f"Model {model_to_use} failed, fallback disabled"
                }
            )
            raise
        # If primary model fails after all retries, log WARNING and try fallback ONCE
        if fallback_to_use != model_to_use:
            logger.warning(
                f"Primary model failed after all retries, attempting fallback",
                extra={
                    "correlation_id": correlation_id,
                    "org_id": org_id,
                    "selected_model": model_to_use,
                    "primary_model": model_to_use,
                    "fallback_model": fallback_to_use,
                    "error": str(e),
                    "decision_reason": f"Primary model {model_to_use} failed, using fallback {fallback_to_use}"
                }
            )
            used_fallback = True
            try:
                # Fallback: try once with retry (but only if fallback is different)
                response_text, token_usage = _query_llm_with_retry(
                    prompt=prompt,
                    model=fallback_to_use,
                    org_id=org_id,
                    correlation_id=correlation_id
                )
                return response_text, token_usage, used_fallback
            except Exception as fallback_error:
                # Fallback also failed - this is final failure
                logger.error(
                    f"Fallback model also failed after all retries",
                    extra={
                        "correlation_id": correlation_id,
                        "org_id": org_id,
                        "selected_model": model_to_use,
                        "primary_model": model_to_use,
                        "fallback_model": fallback_to_use,
                        "actual_model_used": None,
                        "error": str(fallback_error),
                        "decision_reason": f"Both primary {model_to_use} and fallback {fallback_to_use} failed"
                    },
                    exc_info=True
                )
                raise fallback_error
        else:
            # No fallback available, log WARNING and re-raise original error
            logger.warning(
                f"Primary model failed after all retries, no fallback available",
                extra={
                    "correlation_id": correlation_id,
                    "org_id": org_id,
                    "selected_model": model_to_use,
                    "primary_model": model_to_use,
                    "actual_model_used": None,
                    "error": str(e),
                    "decision_reason": f"Model {model_to_use} failed, no fallback configured"
                }
            )
            raise

def _query_llm_with_retry(
    prompt: str,
    model: str,
    org_id: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> Tuple[str, Dict]:
    """
    Query LLM with exponential backoff retry.
    
    Args:
        prompt: The prompt to send to the LLM
        model: Model name to use
        org_id: Organization ID for logging
        correlation_id: Correlation ID for logging
    
    Returns:
        tuple: (response_text, token_usage_dict)
    """
    backoff = INITIAL_BACKOFF
    last_exception = None
    
    for attempt in range(MAX_RETRIES):
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",  # Force JSON output mode
                "options": {
                    "num_predict": 512,  # Limit token output (prevents long-running generations)
                    "temperature": 0.2,  # Lower temperature for more deterministic output
                    "num_ctx": 2048  # Reduced context window for faster processing
                }
            }

            response = requests.post(OLLAMA_URL, json=payload, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            result = response.json()
            response_text = result.get("response", "")
            
            # Extract token usage if available (Ollama API provides these fields)
            prompt_eval_count = result.get("prompt_eval_count") or 0
            eval_count = result.get("eval_count") or 0
            
            token_usage = {
                "prompt_eval_count": prompt_eval_count if result.get("prompt_eval_count") is not None else None,
                "eval_count": eval_count if result.get("eval_count") is not None else None,
                "total_tokens": prompt_eval_count + eval_count
            }
            
            # Log retry if not first attempt
            if attempt > 0:
                logger.info(
                    f"LLM query succeeded on retry",
                    extra={
                        "correlation_id": correlation_id,
                        "org_id": org_id,
                        "model": model,
                        "attempt": attempt + 1
                    }
                )
            
            return response_text, token_usage
            
        except requests.exceptions.ReadTimeout as e:
            # Fail fast on timeout - no retry queue amplification
            logger.warning(
                f"LLM timeout — failing fast",
                extra={
                    "correlation_id": correlation_id,
                    "org_id": org_id,
                    "model": model,
                    "attempt": attempt + 1,
                    "timeout": REQUEST_TIMEOUT
                }
            )
            raise
        except Exception as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                # Exponential backoff
                wait_time = min(backoff, MAX_BACKOFF)
                logger.warning(
                    f"LLM query failed, retrying",
                    extra={
                        "correlation_id": correlation_id,
                        "org_id": org_id,
                        "model": model,
                        "attempt": attempt + 1,
                        "max_retries": MAX_RETRIES,
                        "wait_time": wait_time,
                        "error": str(e)
                    }
                )
                time.sleep(wait_time)
                backoff *= BACKOFF_MULTIPLIER
            else:
                # Last attempt failed - log WARNING (fallback will be attempted by caller)
                logger.warning(
                    f"LLM query failed after all retries",
                    extra={
                        "correlation_id": correlation_id,
                        "org_id": org_id,
                        "model": model,
                        "attempts": MAX_RETRIES,
                        "error": str(e)
                    }
                )
    
    # All retries exhausted
    raise last_exception
