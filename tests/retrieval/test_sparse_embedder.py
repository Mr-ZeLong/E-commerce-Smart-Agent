import pytest
from qdrant_client import models

from app.retrieval.sparse_embedder import SparseTextEmbedder


@pytest.mark.asyncio
async def test_sparse_embedder_produces_qdrant_sparse_vectors():
    embedder = SparseTextEmbedder()
    texts = ["hello world", "电商退换货政策"]
    results = await embedder.aembed(texts)

    assert len(results) == 2
    for vec in results:
        assert isinstance(vec, models.SparseVector)
        assert len(vec.indices) > 0
        assert len(vec.values) > 0
        assert len(vec.indices) == len(vec.values)
