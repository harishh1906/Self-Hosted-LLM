import os
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue
import uuid
import logging

logger = logging.getLogger(__name__)

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = "security_knowledge"

try:
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
except Exception as e:
    logger.warning(f"Qdrant connection failed at startup: {e}. RAG will be unavailable.")
    client = None

def init_collection():
    if client is None:
        logger.warning("Qdrant unavailable — skipping collection init")
        return
    try:
        collections = client.get_collections().collections
        if COLLECTION_NAME not in [c.name for c in collections]:
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )
            logger.info(f"Created Qdrant collection: {COLLECTION_NAME}")
    except Exception as e:
        logger.warning(f"Could not init Qdrant collection: {e}")

def upsert_document(doc_id: str, vector: list, payload: dict):
    if client is None:
        return
    try:
        point_id = str(uuid.uuid4())
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={**payload, "source_id": doc_id}
                )
            ]
        )
    except Exception as e:
        logger.warning(f"Qdrant upsert failed: {e}")

def search_similar(vector: list, limit: int = 5, org_id: str = None):
    if client is None:
        return []
    try:
        query_filter = None
        if org_id:
            query_filter = Filter(
                must=[FieldCondition(key="org_id", match=MatchValue(value=org_id))]
            )
        return client.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            query_filter=query_filter,
            limit=limit
        )
    except Exception as e:
        logger.warning(f"Qdrant search failed: {e}")
        return []
