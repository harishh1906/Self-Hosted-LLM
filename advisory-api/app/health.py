"""
Health and Readiness Checks
Internal endpoints for monitoring service dependencies.
"""
import time
import requests
from sqlalchemy import text
from app.db.database import engine
from app.vector_store import client, COLLECTION_NAME
from app.ollama_client import OLLAMA_URL, MODEL_NAME

def check_ollama_health() -> dict:
    """
    Check if Ollama LLM is available and model is loaded.
    Verifies model is actually loaded (not just available in list).
    """
    try:
        # Step 1: Check if Ollama is responding
        start_time = time.time()
        response = requests.get("http://ollama:11434/api/tags", timeout=2)
        response.raise_for_status()
        models = response.json().get("models", [])
        
        # Step 2: Check if our model is in the list
        model_in_list = any(m.get("name") == MODEL_NAME for m in models)
        
        if not model_in_list:
            return {
                "status": "unhealthy",
                "model_available": False,
                "model_loaded": False,
                "model_name": MODEL_NAME,
                "error": f"Model {MODEL_NAME} not found in available models",
                "response_time_ms": (time.time() - start_time) * 1000
            }
        
        # Step 3: Verify model is actually loaded (can respond to a minimal request)
        try:
            test_response = requests.post(
                "http://ollama:11434/api/generate",
                json={
                    "model": MODEL_NAME,
                    "prompt": "test",
                    "stream": False
                },
                timeout=5
            )
            model_loaded = test_response.status_code == 200
        except Exception as e:
            model_loaded = False
            load_error = str(e)
        
        response_time = (time.time() - start_time) * 1000
        
        if model_loaded:
            return {
                "status": "healthy",
                "model_available": True,
                "model_loaded": True,
                "model_name": MODEL_NAME,
                "response_time_ms": response_time
            }
        else:
            return {
                "status": "degraded",
                "model_available": True,
                "model_loaded": False,
                "model_name": MODEL_NAME,
                "error": f"Model listed but not responding: {load_error if 'load_error' in locals() else 'unknown'}",
                "response_time_ms": response_time
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "model_available": False,
            "model_loaded": False,
            "model_name": MODEL_NAME,
            "error": str(e),
            "response_time_ms": 0
        }

def check_qdrant_health() -> dict:
    """Check if Qdrant vector database is available."""
    try:
        start_time = time.time()
        # Try to get collections (lightweight operation)
        collections = client.get_collections()
        response_time = (time.time() - start_time) * 1000
        
        # Check if our collection exists
        collection_exists = COLLECTION_NAME in [c.name for c in collections.collections]
        
        return {
            "status": "healthy" if collection_exists else "degraded",
            "collection_exists": collection_exists,
            "collection_name": COLLECTION_NAME,
            "response_time_ms": response_time
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "collection_name": COLLECTION_NAME
        }

def check_postgres_health() -> dict:
    """Check if PostgreSQL database is available."""
    try:
        start_time = time.time()
        # Simple query to check connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        response_time = (time.time() - start_time) * 1000
        
        return {
            "status": "healthy",
            "response_time_ms": response_time
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

def get_readiness_status() -> dict:
    """Get overall readiness status of all dependencies."""
    ollama = check_ollama_health()
    qdrant = check_qdrant_health()
    postgres = check_postgres_health()
    
    # Overall status: healthy if all critical services are healthy
    overall_status = "ready"
    if ollama["status"] != "healthy":
        overall_status = "not_ready"  # LLM is critical
    if postgres["status"] != "healthy":
        overall_status = "not_ready"  # Database is critical
    # Qdrant can be degraded (RAG optional)
    
    return {
        "status": overall_status,
        "services": {
            "ollama": ollama,
            "qdrant": qdrant,
            "postgres": postgres
        }
    }

