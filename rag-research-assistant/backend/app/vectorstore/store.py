"""
Vector Store Module
Abstraction layer over FAISS and ChromaDB.
Handles embedding storage, similarity search, and index management.
"""
import os
import uuid
import pickle
from typing import List, Optional, Tuple, Dict, Any
from abc import ABC, abstractmethod
from pathlib import Path
import numpy as np
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class VectorStoreBase(ABC):
    """Abstract base for all vector store backends."""

    @abstractmethod
    async def add_embeddings(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        texts: List[str],
    ) -> bool:
        pass

    @abstractmethod
    async def similarity_search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        score_threshold: float = 0.0,
        filter_metadata: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def delete_by_ids(self, ids: List[str]) -> bool:
        pass

    @abstractmethod
    async def get_collection_stats(self) -> Dict[str, Any]:
        pass


class FAISSVectorStore(VectorStoreBase):
    """
    FAISS-based vector store with persistence.
    Uses IndexFlatIP (inner product / cosine similarity) with normalized vectors.
    """

    def __init__(self):
        self.index = None
        self.id_to_metadata: Dict[str, Dict] = {}
        self.id_to_text: Dict[str, str] = {}
        self.ids: List[str] = []          # ordered list matching FAISS internal IDs
        self.index_path = Path(settings.FAISS_INDEX_PATH)
        self.index_path.mkdir(parents=True, exist_ok=True)
        self._load_index()

    def _load_index(self) -> None:
        index_file = self.index_path / "index.faiss"
        meta_file = self.index_path / "metadata.pkl"
        try:
            import faiss
            if index_file.exists() and meta_file.exists():
                self.index = faiss.read_index(str(index_file))
                with open(meta_file, "rb") as f:
                    data = pickle.load(f)
                    self.id_to_metadata = data.get("id_to_metadata", {})
                    self.id_to_text = data.get("id_to_text", {})
                    self.ids = data.get("ids", [])
                logger.info("FAISS index loaded", vectors=self.index.ntotal)
            else:
                logger.info("No existing FAISS index found, will create on first add")
        except Exception as e:
            logger.error("Failed to load FAISS index", error=str(e))

    def _save_index(self) -> None:
        import faiss
        if self.index is None:
            return
        index_file = self.index_path / "index.faiss"
        meta_file = self.index_path / "metadata.pkl"
        faiss.write_index(self.index, str(index_file))
        with open(meta_file, "wb") as f:
            pickle.dump(
                {
                    "id_to_metadata": self.id_to_metadata,
                    "id_to_text": self.id_to_text,
                    "ids": self.ids,
                },
                f,
            )

    async def add_embeddings(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        texts: List[str],
    ) -> bool:
        try:
            import faiss
            vectors = np.array(embeddings, dtype=np.float32)
            # Normalize for cosine similarity via inner product
            faiss.normalize_L2(vectors)
            dim = vectors.shape[1]

            if self.index is None:
                self.index = faiss.IndexFlatIP(dim)

            self.index.add(vectors)
            for i, vid in enumerate(ids):
                self.ids.append(vid)
                self.id_to_metadata[vid] = metadatas[i]
                self.id_to_text[vid] = texts[i]

            self._save_index()
            logger.info("Added embeddings to FAISS", count=len(ids))
            return True
        except Exception as e:
            logger.error("FAISS add_embeddings failed", error=str(e))
            return False

    async def similarity_search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        score_threshold: float = 0.0,
        filter_metadata: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        if self.index is None or self.index.ntotal == 0:
            return []
        try:
            import faiss
            query = np.array([query_embedding], dtype=np.float32)
            faiss.normalize_L2(query)

            fetch_k = min(top_k * 3, self.index.ntotal)  # over-fetch for filtering
            scores, indices = self.index.search(query, fetch_k)

            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx == -1 or float(score) < score_threshold:
                    continue
                if idx >= len(self.ids):
                    continue
                vid = self.ids[idx]
                metadata = self.id_to_metadata.get(vid, {})

                # Apply metadata filter
                if filter_metadata:
                    if not all(metadata.get(k) == v for k, v in filter_metadata.items()):
                        continue

                results.append(
                    {
                        "id": vid,
                        "score": float(score),
                        "text": self.id_to_text.get(vid, ""),
                        "metadata": metadata,
                    }
                )
                if len(results) >= top_k:
                    break

            return results
        except Exception as e:
            logger.error("FAISS similarity_search failed", error=str(e))
            return []

    async def delete_by_ids(self, ids: List[str]) -> bool:
        """
        FAISS flat index doesn't support deletion natively.
        We rebuild the index excluding the deleted IDs.
        """
        try:
            import faiss
            ids_set = set(ids)
            remaining_ids = [vid for vid in self.ids if vid not in ids_set]

            if not remaining_ids:
                dim = self.index.d if self.index else 1536
                self.index = faiss.IndexFlatIP(dim)
                self.ids = []
                self.id_to_metadata = {}
                self.id_to_text = {}
                self._save_index()
                return True

            # Reconstruct index from remaining vectors
            # For large indexes, this is slow — in production use IndexIDMap
            remaining_indices = [i for i, vid in enumerate(self.ids) if vid not in ids_set]
            vectors = np.zeros((len(remaining_indices), self.index.d), dtype=np.float32)
            for new_i, old_i in enumerate(remaining_indices):
                self.index.reconstruct(old_i, vectors[new_i])

            dim = self.index.d
            self.index = faiss.IndexFlatIP(dim)
            self.index.add(vectors)
            self.ids = remaining_ids
            self.id_to_metadata = {k: v for k, v in self.id_to_metadata.items() if k not in ids_set}
            self.id_to_text = {k: v for k, v in self.id_to_text.items() if k not in ids_set}
            self._save_index()
            logger.info("Deleted from FAISS index", deleted=len(ids))
            return True
        except Exception as e:
            logger.error("FAISS delete failed", error=str(e))
            return False

    async def get_collection_stats(self) -> Dict[str, Any]:
        return {
            "backend": "faiss",
            "total_vectors": self.index.ntotal if self.index else 0,
            "dimension": self.index.d if self.index else 0,
            "index_path": str(self.index_path),
        }


class ChromaVectorStore(VectorStoreBase):
    """ChromaDB-based vector store."""

    def __init__(self):
        import chromadb
        self.client = chromadb.HttpClient(
            host=settings.CHROMA_HOST, port=settings.CHROMA_PORT
        )
        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaDB connected", collection=settings.CHROMA_COLLECTION_NAME)

    async def add_embeddings(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        texts: List[str],
    ) -> bool:
        try:
            # Chroma requires string metadata values
            clean_meta = [
                {k: str(v) for k, v in m.items()} for m in metadatas
            ]
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=clean_meta,
                documents=texts,
            )
            return True
        except Exception as e:
            logger.error("Chroma add_embeddings failed", error=str(e))
            return False

    async def similarity_search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        score_threshold: float = 0.0,
        filter_metadata: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        try:
            where = {k: str(v) for k, v in filter_metadata.items()} if filter_metadata else None
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
            output = []
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i]
                score = 1.0 - distance  # Convert cosine distance to similarity
                if score < score_threshold:
                    continue
                output.append(
                    {
                        "id": doc_id,
                        "score": score,
                        "text": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                    }
                )
            return output
        except Exception as e:
            logger.error("Chroma similarity_search failed", error=str(e))
            return []

    async def delete_by_ids(self, ids: List[str]) -> bool:
        try:
            self.collection.delete(ids=ids)
            return True
        except Exception as e:
            logger.error("Chroma delete failed", error=str(e))
            return False

    async def get_collection_stats(self) -> Dict[str, Any]:
        try:
            count = self.collection.count()
            return {"backend": "chroma", "total_vectors": count}
        except Exception:
            return {"backend": "chroma", "total_vectors": -1}


# Singleton instance
_vector_store: Optional[VectorStoreBase] = None


def get_vector_store() -> VectorStoreBase:
    """Return the configured vector store singleton."""
    global _vector_store
    if _vector_store is None:
        if settings.VECTOR_STORE_TYPE == "chroma":
            _vector_store = ChromaVectorStore()
        else:
            _vector_store = FAISSVectorStore()
    return _vector_store
