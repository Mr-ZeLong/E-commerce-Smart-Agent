import httpx
from pydantic import BaseModel


class RerankResult(BaseModel):
    index: int
    score: float


class QwenReranker:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 10.0,
        max_document_chars: int = 12000,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_document_chars = max_document_chars

    def _truncate(self, text: str) -> str:
        if len(text) > self.max_document_chars:
            return text[: self.max_document_chars]
        return text

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int = 5,
    ) -> list[RerankResult]:
        truncated_docs = [self._truncate(d) for d in documents]
        payload = {
            "model": self.model,
            "query": query,
            "documents": truncated_docs,
            "top_n": top_n,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/reranks",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        raw_results = data.get("results", [])

        results = []
        for item in raw_results:
            idx = item.get("index")
            score = item.get("relevance_score")
            if idx is not None and score is not None:
                results.append(RerankResult(index=int(idx), score=float(score)))

        return results
