"""
Document Processor
Handles parsing of PDF, DOCX, TXT, and Markdown files.
Implements intelligent chunking with overlap for optimal RAG retrieval.
"""
import re
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class DocumentChunkData:
    """Data container for a processed text chunk."""
    def __init__(
        self,
        content: str,
        chunk_index: int,
        start_char: int,
        end_char: int,
        page_number: Optional[int] = None,
        metadata: Optional[Dict] = None,
    ):
        self.content = content
        self.chunk_index = chunk_index
        self.start_char = start_char
        self.end_char = end_char
        self.page_number = page_number
        self.metadata = metadata or {}
        self.token_count = len(content.split())  # rough estimate


class DocumentProcessor:
    """
    Parses documents and splits them into overlapping chunks
    suitable for embedding and semantic search.
    """

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
    ):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    # -------------------------
    # Public entrypoint
    # -------------------------
    async def process_file(
        self, file_path: str, doc_type: str
    ) -> Tuple[str, List[DocumentChunkData], Dict[str, Any]]:
        """
        Parse a file and return (full_text, chunks, metadata).

        Args:
            file_path: Absolute path to the file.
            doc_type:  One of 'pdf', 'docx', 'txt', 'md'.

        Returns:
            Tuple of (full_text, list_of_chunks, metadata_dict)
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        doc_type = doc_type.lower().lstrip(".")

        if doc_type == "pdf":
            full_text, page_texts, metadata = await self._parse_pdf(path)
        elif doc_type == "docx":
            full_text, page_texts, metadata = await self._parse_docx(path)
        elif doc_type in ("txt", "text"):
            full_text, page_texts, metadata = await self._parse_txt(path)
        elif doc_type in ("md", "markdown"):
            full_text, page_texts, metadata = await self._parse_markdown(path)
        else:
            raise ValueError(f"Unsupported document type: {doc_type}")

        metadata["file_hash"] = self._hash_file(path)
        metadata["total_words"] = len(full_text.split())

        chunks = self._split_into_chunks(full_text, page_texts)
        logger.info(
            "Document processed",
            file=path.name,
            chunks=len(chunks),
            words=metadata["total_words"],
        )
        return full_text, chunks, metadata

    # -------------------------
    # Parsers
    # -------------------------
    async def _parse_pdf(
        self, path: Path
    ) -> Tuple[str, List[Tuple[str, int]], Dict]:
        """Extract text from PDF, preserving page structure."""
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            page_texts: List[Tuple[str, int]] = []
            all_text_parts: List[str] = []

            for page_num, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                text = self._clean_text(text)
                if text.strip():
                    page_texts.append((text, page_num))
                    all_text_parts.append(text)

            full_text = "\n\n".join(all_text_parts)
            metadata = {
                "total_pages": len(reader.pages),
                "author": reader.metadata.get("/Author", ""),
                "title": reader.metadata.get("/Title", ""),
                "subject": reader.metadata.get("/Subject", ""),
            }
            return full_text, page_texts, metadata
        except Exception as e:
            logger.error("PDF parsing failed", path=str(path), error=str(e))
            raise

    async def _parse_docx(
        self, path: Path
    ) -> Tuple[str, List[Tuple[str, int]], Dict]:
        """Extract text from DOCX preserving paragraph structure."""
        try:
            from docx import Document
            doc = Document(str(path))
            paragraphs = []
            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    paragraphs.append(text)

            full_text = "\n\n".join(paragraphs)
            # DOCX has no native page concept; treat as single "page"
            page_texts = [(full_text, 1)]
            metadata = {
                "total_pages": 1,
                "author": doc.core_properties.author or "",
                "title": doc.core_properties.title or "",
                "paragraph_count": len(paragraphs),
            }
            return full_text, page_texts, metadata
        except Exception as e:
            logger.error("DOCX parsing failed", path=str(path), error=str(e))
            raise

    async def _parse_txt(
        self, path: Path
    ) -> Tuple[str, List[Tuple[str, int]], Dict]:
        """Parse plain text file."""
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            content = self._clean_text(content)
            page_texts = [(content, 1)]
            metadata = {
                "total_pages": 1,
                "line_count": content.count("\n"),
            }
            return content, page_texts, metadata
        except Exception as e:
            logger.error("TXT parsing failed", path=str(path), error=str(e))
            raise

    async def _parse_markdown(
        self, path: Path
    ) -> Tuple[str, List[Tuple[str, int]], Dict]:
        """Parse Markdown, stripping markup for clean text."""
        import markdown
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
            # Convert to HTML then strip tags for clean plain text
            html = markdown.markdown(raw)
            clean = re.sub(r"<[^>]+>", " ", html)
            clean = self._clean_text(clean)
            page_texts = [(clean, 1)]
            metadata = {
                "total_pages": 1,
                "has_headers": bool(re.search(r"^#{1,6}\s", raw, re.MULTILINE)),
            }
            return clean, page_texts, metadata
        except Exception as e:
            logger.error("Markdown parsing failed", path=str(path), error=str(e))
            raise

    # -------------------------
    # Chunking
    # -------------------------
    def _split_into_chunks(
        self,
        full_text: str,
        page_texts: List[Tuple[str, int]],
    ) -> List[DocumentChunkData]:
        """
        Split text into overlapping chunks.
        Tries to split on sentence/paragraph boundaries for coherent chunks.
        """
        chunks: List[DocumentChunkData] = []
        chunk_index = 0

        # Build page boundary map: character offset → page number
        page_boundary_map = self._build_page_map(page_texts)

        # Split on double newlines (paragraphs) first, then by size
        paragraphs = re.split(r"\n{2,}", full_text)
        buffer = ""
        buffer_start = 0
        char_offset = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                char_offset += 2
                continue

            # If adding this paragraph exceeds chunk_size, flush and start new
            if buffer and len(buffer) + len(para) + 2 > self.chunk_size:
                page_num = self._get_page_for_offset(page_boundary_map, buffer_start)
                chunks.append(
                    DocumentChunkData(
                        content=buffer.strip(),
                        chunk_index=chunk_index,
                        start_char=buffer_start,
                        end_char=buffer_start + len(buffer),
                        page_number=page_num,
                    )
                )
                chunk_index += 1

                # Overlap: retain last N characters
                overlap_text = buffer[-self.chunk_overlap:] if len(buffer) > self.chunk_overlap else buffer
                buffer = overlap_text + "\n\n" + para
                buffer_start = char_offset - len(overlap_text)
            else:
                if buffer:
                    buffer += "\n\n" + para
                else:
                    buffer = para
                    buffer_start = char_offset

            char_offset += len(para) + 2  # +2 for "\n\n"

            # Handle very long paragraphs by splitting them
            if len(buffer) > self.chunk_size * 2:
                sub_chunks = self._split_long_text(buffer, buffer_start, chunk_index, page_boundary_map)
                chunks.extend(sub_chunks)
                chunk_index += len(sub_chunks)
                buffer = ""
                buffer_start = char_offset

        # Flush remaining buffer
        if buffer.strip():
            page_num = self._get_page_for_offset(page_boundary_map, buffer_start)
            chunks.append(
                DocumentChunkData(
                    content=buffer.strip(),
                    chunk_index=chunk_index,
                    start_char=buffer_start,
                    end_char=buffer_start + len(buffer),
                    page_number=page_num,
                )
            )

        return chunks[: settings.MAX_CHUNKS_PER_DOC]

    def _split_long_text(
        self,
        text: str,
        start_offset: int,
        start_index: int,
        page_map: Dict,
    ) -> List[DocumentChunkData]:
        """Split a long text by sentence boundaries."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks = []
        buffer = ""
        buffer_start = start_offset
        chunk_index = start_index

        for sentence in sentences:
            if len(buffer) + len(sentence) > self.chunk_size and buffer:
                page_num = self._get_page_for_offset(page_map, buffer_start)
                chunks.append(
                    DocumentChunkData(
                        content=buffer.strip(),
                        chunk_index=chunk_index,
                        start_char=buffer_start,
                        end_char=buffer_start + len(buffer),
                        page_number=page_num,
                    )
                )
                chunk_index += 1
                overlap = buffer[-self.chunk_overlap:]
                buffer = overlap + " " + sentence
                buffer_start = buffer_start + len(buffer) - len(overlap)
            else:
                buffer += " " + sentence if buffer else sentence

        if buffer.strip():
            page_num = self._get_page_for_offset(page_map, buffer_start)
            chunks.append(
                DocumentChunkData(
                    content=buffer.strip(),
                    chunk_index=chunk_index,
                    start_char=buffer_start,
                    end_char=buffer_start + len(buffer),
                    page_number=page_num,
                )
            )
        return chunks

    # -------------------------
    # Helpers
    # -------------------------
    def _build_page_map(self, page_texts: List[Tuple[str, int]]) -> Dict[int, int]:
        """Map character offsets to page numbers."""
        page_map: Dict[int, int] = {}
        offset = 0
        for text, page_num in page_texts:
            page_map[offset] = page_num
            offset += len(text) + 2
        return page_map

    def _get_page_for_offset(self, page_map: Dict[int, int], offset: int) -> int:
        """Find which page a character offset belongs to."""
        page = 1
        for boundary, page_num in sorted(page_map.items()):
            if offset >= boundary:
                page = page_num
            else:
                break
        return page

    @staticmethod
    def _clean_text(text: str) -> str:
        """Normalize whitespace and remove control characters."""
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        text = re.sub(r" {2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _hash_file(path: Path) -> str:
        """Compute SHA-256 hash of a file for deduplication."""
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                sha256.update(block)
        return sha256.hexdigest()
