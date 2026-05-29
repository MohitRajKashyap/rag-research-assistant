"""
RAG Pipeline
Core retrieval-augmented generation engine using LangChain.
Implements: semantic search → context ranking → prompt engineering → generation.
"""
import time
import uuid
from typing import List, Optional, AsyncGenerator, Dict, Any
import structlog
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.redis import query_cache
from app.vectorstore.store import get_vector_store
from app.vectorstore.embeddings import get_embedding_service
from app.schemas.conversation import MessageSource

logger = structlog.get_logger(__name__)


# -------------------------------------------------------
# Prompt Templates
# -------------------------------------------------------
SYSTEM_PROMPT = """You are an expert AI Research Assistant with deep knowledge across scientific domains.
Your role is to provide accurate, well-reasoned answers grounded in the provided research documents.

RULES:
1. Base your answers on the CONTEXT provided below. Do not fabricate information.
2. If the context doesn't contain enough information, say so honestly.
3. Always cite your sources using [Source N] notation.
4. Be concise yet comprehensive. Use bullet points for clarity when appropriate.
5. For technical topics, explain concepts clearly for an academic audience.
6. If asked a follow-up question, use both context and conversation history.

CONTEXT FROM RESEARCH DOCUMENTS:
{context}

Remember: Ground every claim in the provided documents. Accuracy over completeness."""

QUERY_REFINEMENT_PROMPT = """Given this user question and conversation history, 
rephrase the question to be more specific and searchable for a vector database.
Return ONLY the refined query, nothing else.

Conversation history:
{history}

Current question: {question}
Refined query:"""

NO_CONTEXT_RESPONSE = """I couldn't find relevant information in your research documents to answer this question.

This could mean:
- The topic hasn't been covered in the uploaded documents
- The documents haven't been fully indexed yet
- Try rephrasing your question with different keywords

You can upload more documents or ask about topics covered in your research library."""


class RAGPipeline:
    """
    Full RAG pipeline:
      1. Query embedding
      2. Vector similarity search
      3. Context re-ranking
      4. Prompt assembly
      5. LLM generation (streaming or batch)
    """

    def __init__(self):
        self.openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.embedding_service = get_embedding_service()
        self.vector_store = get_vector_store()
        self.model = settings.OPENAI_MODEL
        self.max_tokens = settings.OPENAI_MAX_TOKENS
        self.temperature = settings.OPENAI_TEMPERATURE
        self.top_k = settings.RAG_TOP_K
        self.score_threshold = settings.RAG_SCORE_THRESHOLD

    # -------------------------------------------------------
    # Main entry points
    # -------------------------------------------------------
    async def query(
        self,
        question: str,
        conversation_history: Optional[List[Dict]] = None,
        collection_id: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Non-streaming RAG query.
        Returns: {content, sources, tokens_used, latency_ms, model}
        """
        start = time.time()
        top_k = top_k or self.top_k

        # 1. Refine the query using conversation context
        refined_query = await self._refine_query(question, conversation_history or [])

        # 2. Check cache
        cache_key = f"{refined_query}:{collection_id}:{top_k}"
        cached = await query_cache.get(cache_key)
        if cached:
            logger.info("RAG cache hit", query=refined_query[:50])
            cached["latency_ms"] = int((time.time() - start) * 1000)
            return cached

        # 3. Retrieve relevant chunks
        sources, context_text = await self._retrieve_context(
            refined_query, top_k=top_k, collection_id=collection_id
        )

        # 4. Build messages
        messages = self._build_messages(
            question=question,
            context=context_text,
            history=conversation_history or [],
        )

        # 5. Generate response
        if not sources:
            content = NO_CONTEXT_RESPONSE
            tokens_used = 0
        else:
            content, tokens_used = await self._generate(messages)

        latency_ms = int((time.time() - start) * 1000)
        result = {
            "content": content,
            "sources": [s.model_dump() for s in sources],
            "tokens_used": tokens_used,
            "latency_ms": latency_ms,
            "model": self.model,
        }

        # Cache successful responses
        if sources:
            await query_cache.set(cache_key, result, ttl=1800)

        logger.info(
            "RAG query complete",
            latency_ms=latency_ms,
            sources=len(sources),
            tokens=tokens_used,
        )
        return result

    async def stream_query(
        self,
        question: str,
        conversation_history: Optional[List[Dict]] = None,
        collection_id: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streaming RAG query — yields chunks as they are generated.
        Yields dicts with keys: type, content, sources, conversation_id, error
        """
        top_k = top_k or self.top_k

        # Refine query
        refined_query = await self._refine_query(question, conversation_history or [])

        # Retrieve context
        sources, context_text = await self._retrieve_context(
            refined_query, top_k=top_k, collection_id=collection_id
        )

        # Yield sources first so client can display them immediately
        yield {
            "type": "sources",
            "sources": [s.model_dump() for s in sources],
        }

        if not sources:
            yield {"type": "token", "content": NO_CONTEXT_RESPONSE}
            yield {"type": "done"}
            return

        messages = self._build_messages(question, context_text, conversation_history or [])

        try:
            stream = await self.openai.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield {"type": "token", "content": delta.content}

            yield {"type": "done"}
        except Exception as e:
            logger.error("Streaming generation failed", error=str(e))
            yield {"type": "error", "error": str(e)}

    # -------------------------------------------------------
    # Internal methods
    # -------------------------------------------------------
    async def _refine_query(
        self, question: str, history: List[Dict]
    ) -> str:
        """
        Use LLM to refine a query given conversation context.
        Improves retrieval quality for follow-up questions.
        """
        if not history or len(history) == 0:
            return question  # First turn — no refinement needed

        try:
            history_str = "\n".join(
                f"{m['role'].upper()}: {m['content'][:200]}"
                for m in history[-4:]  # last 2 turns
            )
            prompt = QUERY_REFINEMENT_PROMPT.format(
                history=history_str, question=question
            )
            response = await self.openai.chat.completions.create(
                model="gpt-3.5-turbo",  # cheap model for refinement
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.0,
            )
            refined = response.choices[0].message.content.strip()
            logger.debug("Query refined", original=question[:50], refined=refined[:50])
            return refined or question
        except Exception as e:
            logger.warning("Query refinement failed, using original", error=str(e))
            return question

    async def _retrieve_context(
        self,
        query: str,
        top_k: int,
        collection_id: Optional[str] = None,
    ) -> tuple[List[MessageSource], str]:
        """
        Embed query and retrieve top-k similar chunks from vector store.
        Returns (sources, formatted_context_string).
        """
        query_embedding = await self.embedding_service.embed_text(query)
        if not query_embedding:
            return [], ""

        filter_metadata = None
        if collection_id:
            filter_metadata = {"collection_id": str(collection_id)}

        raw_results = await self.vector_store.similarity_search(
            query_embedding=query_embedding,
            top_k=top_k,
            score_threshold=self.score_threshold,
            filter_metadata=filter_metadata,
        )

        if not raw_results:
            return [], ""

        # Re-rank: apply simple diversity filter (avoid same-document duplicates)
        if settings.ENABLE_RERANKING:
            raw_results = self._rerank_results(raw_results)

        sources: List[MessageSource] = []
        context_parts: List[str] = []

        for i, result in enumerate(raw_results, start=1):
            meta = result.get("metadata", {})
            source = MessageSource(
                document_id=meta.get("document_id", ""),
                document_title=meta.get("document_title", "Unknown Document"),
                filename=meta.get("filename", ""),
                chunk_content=result["text"][:500],  # Truncate for response
                chunk_index=int(meta.get("chunk_index", 0)),
                page_number=int(meta.get("page_number", 0)) or None,
                similarity_score=round(result["score"], 4),
            )
            sources.append(source)

            context_parts.append(
                f"[Source {i}] {meta.get('document_title', 'Document')} "
                f"(p.{meta.get('page_number', '?')}):\n{result['text']}"
            )

        # Truncate total context to avoid exceeding LLM context window
        context_text = "\n\n---\n\n".join(context_parts)
        if len(context_text) > settings.RAG_MAX_CONTEXT_LENGTH:
            context_text = context_text[: settings.RAG_MAX_CONTEXT_LENGTH] + "\n[...context truncated...]"

        return sources, context_text

    def _rerank_results(self, results: List[Dict]) -> List[Dict]:
        """
        Simple diversity re-ranker.
        Limits chunks per document to avoid context domination by a single source.
        """
        seen_docs: Dict[str, int] = {}
        max_per_doc = 2
        reranked = []
        for result in sorted(results, key=lambda r: r["score"], reverse=True):
            doc_id = result.get("metadata", {}).get("document_id", "")
            count = seen_docs.get(doc_id, 0)
            if count < max_per_doc:
                reranked.append(result)
                seen_docs[doc_id] = count + 1
        return reranked

    def _build_messages(
        self, question: str, context: str, history: List[Dict]
    ) -> List[Dict]:
        """Assemble the full messages array for the LLM."""
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT.format(context=context or "No relevant context found."),
            }
        ]
        # Include last N turns of conversation history
        for turn in history[-6:]:
            messages.append({"role": turn["role"], "content": turn["content"][:1000]})

        messages.append({"role": "user", "content": question})
        return messages

    async def _generate(self, messages: List[Dict]) -> tuple[str, int]:
        """Call OpenAI chat completion and return (content, tokens_used)."""
        try:
            response = await self.openai.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=False,
            )
            content = response.choices[0].message.content or ""
            tokens_used = response.usage.total_tokens if response.usage else 0
            return content, tokens_used
        except Exception as e:
            logger.error("LLM generation failed", error=str(e))
            raise


# Singleton
_rag_pipeline: Optional[RAGPipeline] = None


def get_rag_pipeline() -> RAGPipeline:
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline
