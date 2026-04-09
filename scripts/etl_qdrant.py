import asyncio
import glob
import json
import logging
import os
import sys

sys.path.append(os.getcwd())

from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import models
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.retrieval.client import QdrantKnowledgeClient
from app.retrieval.embeddings import embedding_model
from app.retrieval.sparse_embedder import SparseTextEmbedder

logger = logging.getLogger(__name__)
BATCH_SIZE = 50


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def embed_dense_with_retry(texts: list[str]) -> list[list[float]]:
    """Generate dense embeddings with retry."""
    return await embedding_model.aembed_documents(texts)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def embed_sparse_with_retry(sparse_embedder: SparseTextEmbedder, texts: list[str]) -> list[models.SparseVector]:
    """Generate sparse embeddings with retry."""
    return await sparse_embedder.aembed(texts)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def upsert_with_retry(qdrant_client: QdrantKnowledgeClient, points: list[models.PointStruct]):
    """Upsert points to Qdrant with retry."""
    await qdrant_client.upsert_chunks(points)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def recreate_with_retry(qdrant_client: QdrantKnowledgeClient):
    """Recreate Qdrant collection with retry."""
    await qdrant_client.recreate_collection()


def load_documents(file_path: str) -> list[Document]:
    """Load documents from file based on extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".md", ".txt"]:
        return TextLoader(file_path, encoding="utf-8").load()
    elif ext == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        text = json.dumps(data, ensure_ascii=False)
        return [Document(page_content=text, metadata={"source": file_path})]
    else:
        raise ValueError(f"Unsupported file type: {ext}")


async def process_file(
    file_path: str,
    source_name: str,
    qdrant_client: QdrantKnowledgeClient,
    sparse_embedder: SparseTextEmbedder,
    start_id: int,
) -> tuple[int, bool]:
    """Process a single file: load, split, embed, upsert."""
    print(f"🚀 [Start] Processing file: {source_name}")
    next_id = start_id
    try:
        docs = load_documents(file_path)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=512,
            chunk_overlap=50,
            separators=["\n\n", "\n", "。", "！", "？", " ", ""],
        )
        split_docs = text_splitter.split_documents(docs)
        total_chunks = len(split_docs)
        print(f"  📄 Split complete: {total_chunks} chunks")
        if total_chunks == 0:
            print("  ⚠️ Warning: file is empty or unreadable")
            return next_id, True

        for i in range(0, total_chunks, BATCH_SIZE):
            batch_docs = split_docs[i : i + BATCH_SIZE]
            batch_texts = []
            batch_metas = []
            for idx, doc in enumerate(batch_docs):
                cleaned = doc.page_content.strip()
                if cleaned:
                    batch_texts.append(cleaned)
                    page = doc.metadata.get("page", 0) + 1
                    batch_metas.append({"page": page, "chunk_index": i + idx})

            if not batch_texts:
                print(f"  ⚠️ Skipping empty batch {i}")
                continue

            print(f"  🧠 Embedding batch {i // BATCH_SIZE + 1} (valid chunks: {len(batch_texts)})...")
            dense_vectors, sparse_vectors = await asyncio.gather(
                embed_dense_with_retry(batch_texts),
                embed_sparse_with_retry(sparse_embedder, batch_texts),
            )

            points = []
            for j, text in enumerate(batch_texts):
                points.append(models.PointStruct(
                    id=next_id,
                    vector={
                        "dense": dense_vectors[j],
                        "sparse": sparse_vectors[j],
                    },
                    payload={
                        "content": text,
                        "source": source_name,
                        "meta_data": batch_metas[j],
                    },
                ))
                next_id += 1

            await upsert_with_retry(qdrant_client, points)

        print(f"✅ [Done] {source_name} processed")
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception(f"❌ [Error] Failed to process file {file_path}")
        return next_id, False
    return next_id, True


async def main():
    """Main ETL entrypoint."""
    base_dir = "data"
    if not os.path.exists(base_dir):
        raise FileNotFoundError(f"Data directory not found: {base_dir}")

    all_files = []
    for ext in ["*.txt", "*.md", "*.json"]:
        all_files.extend(glob.glob(os.path.join(base_dir, "**", ext), recursive=True))

    print(f"📂 Found {len(all_files)} files to process...")

    qdrant_client = QdrantKnowledgeClient(
        url=settings.QDRANT_URL,
        collection_name="knowledge_chunks",
        api_key=settings.QDRANT_API_KEY,
    )
    try:
        await recreate_with_retry(qdrant_client)
        sparse_embedder = SparseTextEmbedder()

        next_id = 0
        failed_files = []
        for file_path in all_files:
            source_name = os.path.basename(file_path)
            next_id, success = await process_file(file_path, source_name, qdrant_client, sparse_embedder, next_id)
            if not success:
                failed_files.append(source_name)

        if failed_files:
            raise RuntimeError(f"ETL failed for files: {failed_files}")

        print(f"✅ All files processed, total {next_id} chunks written")
    finally:
        await qdrant_client.client.close()


if __name__ == "__main__":
    asyncio.run(main())
