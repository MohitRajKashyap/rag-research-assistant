"""
RAG Pipeline Tests
Tests the full RAG pipeline with mocked OpenAI and vector store.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
class TestRAGPipeline:

    @pytest.fixture
    def mock_pipeline(self):
        with patch("app.rag.pipeline.AsyncOpenAI") as mock_oai, \
             patch("app.rag.pipeline.get_embedding_service") as mock_emb, \
             patch("app.rag.pipeline.get_vector_store") as mock_vs:

            # Mock embedding
            mock_emb.return_value.embed_text = AsyncMock(return_value=[0.1] * 1536)

            # Mock vector store results
            mock_vs.return_value.similarity_search = AsyncMock(return_value=[
                {
                    "id": "chunk-1",
                    "score": 0.92,
                    "text": "Transformers use self-attention mechanisms for language modeling.",
                    "metadata": {
                        "document_id": "doc-123",
                        "document_title": "Attention Is All You Need",
                        "filename": "attention.pdf",
                        "chunk_index": 0,
                        "page_number": 1,
                        "collection_id": "",
                    },
                }
            ])

            # Mock OpenAI chat completion
            completion_mock = MagicMock()
            completion_mock.choices = [MagicMock()]
            completion_mock.choices[0].message.content = "Transformers rely on attention mechanisms."
            completion_mock.usage.total_tokens = 150
            mock_oai.return_value.chat.completions.create = AsyncMock(return_value=completion_mock)

            from app.rag.pipeline import RAGPipeline
            pipeline = RAGPipeline()
            yield pipeline

    async def test_query_returns_content(self, mock_pipeline):
        result = await mock_pipeline.query("What is a transformer?")
        assert "content" in result
        assert len(result["content"]) > 0
        assert "sources" in result
        assert result["tokens_used"] > 0

    async def test_query_returns_sources(self, mock_pipeline):
        result = await mock_pipeline.query("Explain attention mechanism")
        assert len(result["sources"]) == 1
        assert result["sources"][0]["similarity_score"] == 0.92

    async def test_query_with_history(self, mock_pipeline):
        history = [
            {"role": "user", "content": "What is ML?"},
            {"role": "assistant", "content": "Machine learning is a subset of AI."},
        ]
        # Mock the query refinement call (gpt-3.5-turbo)
        refine_mock = MagicMock()
        refine_mock.choices = [MagicMock()]
        refine_mock.choices[0].message.content = "What is machine learning attention?"

        completion_mock = MagicMock()
        completion_mock.choices = [MagicMock()]
        completion_mock.choices[0].message.content = "Attention is a mechanism."
        completion_mock.usage.total_tokens = 100

        mock_pipeline.openai.chat.completions.create = AsyncMock(
            side_effect=[refine_mock, completion_mock]
        )
        result = await mock_pipeline.query("Tell me more", conversation_history=history)
        assert result["content"] == "Attention is a mechanism."

    async def test_no_results_returns_fallback(self, mock_pipeline):
        mock_pipeline.vector_store.similarity_search = AsyncMock(return_value=[])
        result = await mock_pipeline.query("Something not in documents")
        assert "couldn't find" in result["content"].lower() or len(result["sources"]) == 0

    async def test_rerank_limits_per_document(self, mock_pipeline):
        # 3 chunks from same document
        results = [
            {"id": f"c{i}", "score": 0.9 - i*0.01, "text": f"chunk {i}", "metadata": {"document_id": "same-doc"}}
            for i in range(3)
        ]
        reranked = mock_pipeline._rerank_results(results)
        same_doc_count = sum(1 for r in reranked if r["metadata"]["document_id"] == "same-doc")
        assert same_doc_count <= 2  # max 2 per doc


@pytest.mark.asyncio
class TestEmbeddingService:
    async def test_embed_text_caches_result(self):
        from app.vectorstore.embeddings import EmbeddingService
        from unittest.mock import AsyncMock, patch

        with patch("app.vectorstore.embeddings.embedding_cache") as mock_cache, \
             patch("app.vectorstore.embeddings.AsyncOpenAI") as mock_oai:

            # First call: cache miss
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()

            emb_resp = MagicMock()
            emb_resp.data = [MagicMock(embedding=[0.1] * 1536)]
            mock_oai.return_value.embeddings.create = AsyncMock(return_value=emb_resp)

            svc = EmbeddingService()
            result = await svc.embed_text("test text")

            assert len(result) == 1536
            mock_cache.set.assert_called_once()
