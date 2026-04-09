import pytest
from qdrant_client import models
from unittest.mock import patch, MagicMock
import numpy as np

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


@pytest.mark.asyncio
async def test_sparse_embedder_with_mock():
    mock_emb = MagicMock()
    mock_emb.indices = np.array([1, 2, 3])
    mock_emb.values = np.array([0.1, 0.2, 0.3])

    with patch("app.retrieval.sparse_embedder.SparseTextEmbedding") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.embed.return_value = [mock_emb]
        mock_cls.return_value = mock_instance

        embedder = SparseTextEmbedder()
        results = await embedder.aembed(["test"])

        assert len(results) == 1
        assert isinstance(results[0], models.SparseVector)
        assert results[0].indices == [1, 2, 3]
        assert results[0].values == [0.1, 0.2, 0.3]
        mock_cls.assert_called_once()
