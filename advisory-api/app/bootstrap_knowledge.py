from app.embedding import embed_text
from app.vector_store import init_collection, upsert_document

KNOWLEDGE_BASE = [
    {
        "id": "cwe-89",
        "text": "CWE-89 SQL Injection allows attackers to manipulate database queries via unsanitized input."
    },
    {
        "id": "owasp-sql",
        "text": "OWASP recommends parameterized queries, input validation, and least privilege to prevent SQL Injection."
    },
    {
        "id": "nist-ac-3",
        "text": "NIST AC-3 Access Enforcement requires restricting system access to authorized users and transactions."
    }
]

def bootstrap():
    init_collection()
    for item in KNOWLEDGE_BASE:
        vector = embed_text(item["text"])
        upsert_document(
            doc_id=item["id"],
            vector=vector,
            payload={"text": item["text"]}
        )

if __name__ == "__main__":
    bootstrap()
