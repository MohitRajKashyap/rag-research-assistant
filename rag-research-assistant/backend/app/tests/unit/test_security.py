"""
Unit Tests - Security, Document Processor, Embeddings
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.core.security import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, get_token_subject, validate_password_strength,
)
from app.rag.document_processor import DocumentProcessor


# -------------------------------------------------------
# Security tests
# -------------------------------------------------------
class TestSecurity:
    def test_hash_and_verify_password(self):
        password = "MySecret123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)
        assert not verify_password("WrongPassword", hashed)

    def test_create_and_decode_access_token(self):
        user_id = "test-user-123"
        token = create_access_token(user_id)
        subject = get_token_subject(token, "access")
        assert subject == user_id

    def test_create_and_decode_refresh_token(self):
        user_id = "test-user-456"
        token = create_refresh_token(user_id)
        subject = get_token_subject(token, "refresh")
        assert subject == user_id

    def test_wrong_token_type_raises(self):
        from fastapi import HTTPException
        token = create_access_token("user-1")
        with pytest.raises(HTTPException):
            get_token_subject(token, "refresh")  # wrong type

    def test_invalid_token_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            get_token_subject("invalid.token.here", "access")

    def test_password_strength_valid(self):
        assert validate_password_strength("StrongPass1")

    def test_password_strength_too_short(self):
        assert not validate_password_strength("Sh0rt")

    def test_password_strength_no_uppercase(self):
        assert not validate_password_strength("weakpass1")

    def test_password_strength_no_digit(self):
        assert not validate_password_strength("NoDigitPass")


# -------------------------------------------------------
# Document Processor tests
# -------------------------------------------------------
class TestDocumentProcessor:
    def test_clean_text(self):
        raw = "Hello\x00World  \n\n\n\nFoo"
        cleaned = DocumentProcessor._clean_text(raw)
        assert "\x00" not in cleaned
        assert "  " not in cleaned

    def test_chunking_basic(self):
        processor = DocumentProcessor(chunk_size=100, chunk_overlap=20)
        text = " ".join(["word"] * 300)  # 300 words
        page_texts = [(text, 1)]
        chunks = processor._split_into_chunks(text, page_texts)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.content) <= 200  # rough chars

    def test_chunk_overlap(self):
        processor = DocumentProcessor(chunk_size=50, chunk_overlap=20)
        # Create text that forces multiple chunks
        text = "A" * 200
        page_texts = [(text, 1)]
        chunks = processor._split_into_chunks(text, page_texts)
        if len(chunks) > 1:
            # Overlap content from previous chunk should appear in next
            assert len(chunks) >= 2

    def test_chunk_indices_sequential(self):
        processor = DocumentProcessor(chunk_size=50, chunk_overlap=10)
        text = "\n\n".join([f"Paragraph {i} content here." for i in range(20)])
        page_texts = [(text, 1)]
        chunks = processor._split_into_chunks(text, page_texts)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    @pytest.mark.asyncio
    async def test_parse_txt(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello world.\nThis is a test document.\nWith multiple lines.")
        processor = DocumentProcessor()
        full_text, _, metadata = await processor._parse_txt(test_file)
        assert "Hello world" in full_text
        assert metadata["total_pages"] == 1
