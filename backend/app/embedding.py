import logging

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Lazily load and cache the embedding model."""
    global _model
    if _model is None:
        logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
        _model = SentenceTransformer("BAAI/bge-large-en")
        logger.info("Loaded embedding model: BAAI/bge-large-en")
    return _model


def encode(texts: list[str]) -> list[list[float]]:
    """Encode texts into embedding vectors."""
    model = get_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()
