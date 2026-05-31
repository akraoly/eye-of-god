# Future: recherche sémantique par embeddings
# Prévu : sentence-transformers + ChromaDB ou FAISS
#
# Interface planifiée :
#   embed(text: str) -> List[float]
#   add(text: str, metadata: dict) -> str        # returns id
#   search(query: str, k: int = 5) -> List[dict] # returns [{text, score, metadata}]
#   delete(doc_id: str) -> bool


class VectorStore:
    enabled = False

    def embed(self, text: str) -> list:
        raise NotImplementedError("Vector store pas encore activé")

    def search(self, query: str, k: int = 5) -> list:
        raise NotImplementedError("Vector store pas encore activé")


vector_store = VectorStore()
