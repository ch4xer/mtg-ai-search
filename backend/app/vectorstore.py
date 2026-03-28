import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"

import chromadb
from chromadb.utils import embedding_functions

CHROMA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chroma_data")


def get_embedding_function():
    import logging
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="BAAI/bge-large-en",
    )


def get_client():
    return chromadb.PersistentClient(path=CHROMA_DIR)


def get_abilities_collection():
    client = get_client()
    ef = get_embedding_function()
    return client.get_or_create_collection(
        name="keyword_abilities",
        embedding_function=ef,
    )


def get_cards_collection():
    client = get_client()
    ef = get_embedding_function()
    return client.get_or_create_collection(
        name="cards",
        embedding_function=ef,
    )


def search_abilities(query: str, n_results: int = 5, distance_threshold: float | None = None) -> list[dict]:
    """Search ability vectors and return a list of {name, description, distance}.

    If *distance_threshold* is given, only results with distance < threshold are kept.
    """
    collection = get_abilities_collection()
    if collection.count() == 0:
        return []
    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    abilities: list[dict] = []
    if results and results["documents"] and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            distance = results["distances"][0][i] if results.get("distances") else 1.0
            if distance_threshold is not None and distance >= distance_threshold:
                continue
            abilities.append({
                "name": results["metadatas"][0][i]["name"],
                "description": doc,
                "distance": distance,
            })
    return abilities


def search_cards(query: str, n_results: int = 10) -> dict:
    collection = get_cards_collection()
    if collection.count() == 0:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]]}
    results = collection.query(query_texts=[query], n_results=min(n_results, collection.count()))
    return results
