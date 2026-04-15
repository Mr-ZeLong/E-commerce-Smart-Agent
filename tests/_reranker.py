from app.retrieval.reranker import RerankResult


class DeterministicReranker:
    def __init__(self, results=None):
        self._results = results or []

    async def rerank(self, query, documents, top_n=5):
        if self._results:
            return self._results
        return [
            RerankResult(index=i, score=0.99 - i * 0.1) for i in range(min(top_n, len(documents)))
        ]
