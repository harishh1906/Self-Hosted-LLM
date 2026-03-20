import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue

QDRANT_HOST = "qdrant"
QDRANT_PORT = 6333
COLLECTION_NAME = "security_knowledge"

client = QdrantClient(
    host=QDRANT_HOST,
    port=QDRANT_PORT,
)

def init_collection():
    collections = client.get_collections().collections
    if COLLECTION_NAME not in [c.name for c in collections]:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=384,
                distance=Distance.COSINE
            )
        )

def upsert_document(doc_id: str, vector: list[float], payload: dict):
    """
    Qdrant requires numeric or UUID point IDs.
    Store human-readable IDs inside payload.
    """
    point_id = str(uuid.uuid4())

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    **payload,
                    "source_id": doc_id
                }
            )
        ]
    )

def search_similar(vector: list[float], limit: int = 5, org_id: str = None):
    """
    CRITICAL FIX: Make Qdrant fully multi-tenant by filtering by org_id.
    If org_id is provided, only return results for that organization.
    """
    query_filter = None
    if org_id:
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="org_id",
                    match=MatchValue(value=org_id)
                )
            ]
        )
    
    return client.search(
        collection_name=COLLECTION_NAME,
        query_vector=vector,
        query_filter=query_filter,  # Multi-tenant isolation
        limit=limit
    )
