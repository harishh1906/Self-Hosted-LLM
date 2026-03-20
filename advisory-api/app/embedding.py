from sentence_transformers import SentenceTransformer

# Load once per container
_model = SentenceTransformer("all-MiniLM-L6-v2")

def embed_text(text: str) -> list[float]:
    """
    Convert input text into a 384-dimensional embedding vector.
    """
    return _model.encode(text).tolist()
