from dataclasses import dataclass

import httpx

from app.core.config import settings


@dataclass
class RerankResult:
    index: int
    score: float


class QwenReranker:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 10.0,
        max_document_chars: int = 12000,
    ):
        # Use the correct DashScope rerank endpoint, not the OpenAI chat endpoint
        self.base_url = (base_url or "https://dashscope.aliyuncs.com/compatible-api/v1").rstrip("/")
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.RERANK_MODEL
        self.timeout = timeout
        self.max_document_chars = max_document_chars

    def _truncate(self, text: str) -> str:
        if len(text) > self.max_document_chars:
            return text[:self.max_document_chars]
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
        try:
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

            # Handle multiple possible response shapes
            raw_results = data.get("results", [])
            if not raw_results and "output" in data:
                raw_results = (data.get("output") or {}).get("results", [])

            results = []
            for item in raw_results:
                idx = item.get("index")
                if idx is None:
                    idx = item.get("document_index")
                score = item.get("relevance_score")
                if score is None:
                    score = item.get("score")
                if idx is not None and score is not None:
                    results.append(RerankResult(index=int(idx), score=float(score)))

            return results
        except Exception:
            # Fallback to identity ordering on any failure
            return [RerankResult(index=i, score=0.0) for i in range(len(documents))]
