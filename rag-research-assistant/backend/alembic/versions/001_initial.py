"""Initial migration - create all tables

Revision ID: 001_initial
Revises: 
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('username', sa.String(100), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('role', sa.Enum('admin', 'user', 'researcher', name='userrole'), nullable=False, server_default='user'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('is_verified', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('api_key', sa.String(100), nullable=True, unique=True),
        sa.Column('total_queries', sa.Integer, server_default='0'),
        sa.Column('total_tokens_used', sa.Integer, server_default='0'),
        sa.Column('total_documents_uploaded', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_username', 'users', ['username'])
    op.create_index('ix_users_api_key', 'users', ['api_key'])

    # Collections
    op.create_table(
        'collections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('is_public', sa.Boolean, server_default='false'),
        sa.Column('document_count', sa.Integer, server_default='0'),
        sa.Column('color', sa.String(20), server_default='#6366f1'),
        sa.Column('icon', sa.String(50), server_default='folder'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_collections_owner_id', 'collections', ['owner_id'])

    # Documents
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('collection_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('collections.id', ondelete='SET NULL'), nullable=True),
        sa.Column('filename', sa.String(500), nullable=False),
        sa.Column('original_filename', sa.String(500), nullable=False),
        sa.Column('file_path', sa.String(1000), nullable=False),
        sa.Column('file_size', sa.Integer, nullable=False),
        sa.Column('file_hash', sa.String(64), nullable=True),
        sa.Column('doc_type', sa.Enum('pdf', 'docx', 'txt', 'md', name='documenttype'), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('author', sa.String(255), nullable=True),
        sa.Column('total_pages', sa.Integer, nullable=True),
        sa.Column('total_words', sa.Integer, nullable=True),
        sa.Column('language', sa.String(10), nullable=True),
        sa.Column('doc_metadata', postgresql.JSON, nullable=True),
        sa.Column('status', sa.Enum('pending', 'processing', 'indexed', 'failed', name='documentstatus'), server_default='pending'),
        sa.Column('processing_error', sa.Text, nullable=True),
        sa.Column('chunk_count', sa.Integer, server_default='0'),
        sa.Column('is_indexed', sa.Boolean, server_default='false'),
        sa.Column('celery_task_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('indexed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_documents_owner_id', 'documents', ['owner_id'])
    op.create_index('ix_documents_file_hash', 'documents', ['file_hash'])
    op.create_index('ix_documents_status', 'documents', ['status'])

    # Document chunks
    op.create_table(
        'document_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('chunk_index', sa.Integer, nullable=False),
        sa.Column('start_char', sa.Integer, nullable=True),
        sa.Column('end_char', sa.Integer, nullable=True),
        sa.Column('page_number', sa.Integer, nullable=True),
        sa.Column('token_count', sa.Integer, nullable=True),
        sa.Column('vector_id', sa.String(255), nullable=True),
        sa.Column('embedding_model', sa.String(100), nullable=True),
        sa.Column('chunk_metadata', postgresql.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_document_chunks_document_id', 'document_chunks', ['document_id'])
    op.create_index('ix_document_chunks_vector_id', 'document_chunks', ['vector_id'])

    # Conversations
    op.create_table(
        'conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('is_archived', sa.Boolean, server_default='false'),
        sa.Column('message_count', sa.Integer, server_default='0'),
        sa.Column('total_tokens', sa.Integer, server_default='0'),
        sa.Column('conversation_metadata', postgresql.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_conversations_user_id', 'conversations', ['user_id'])

    # Messages
    op.create_table(
        'messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.Enum('user', 'assistant', 'system', name='messagerole'), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('sources', postgresql.JSON, nullable=True),
        sa.Column('tokens_used', sa.Integer, nullable=True),
        sa.Column('retrieval_score', sa.Float, nullable=True),
        sa.Column('latency_ms', sa.Integer, nullable=True),
        sa.Column('model_used', sa.String(100), nullable=True),
        sa.Column('is_bookmarked', sa.Boolean, server_default='false'),
        sa.Column('feedback_rating', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_messages_conversation_id', 'messages', ['conversation_id'])
    op.create_index('ix_messages_created_at', 'messages', ['created_at'])

    # Bookmarks
    op.create_table(
        'bookmarks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('messages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('note', sa.Text, nullable=True),
        sa.Column('tags', postgresql.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Notes
    op.create_table(
        'notes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('tags', postgresql.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # API usage logs
    op.create_table(
        'api_usage_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
        sa.Column('endpoint', sa.String(255), nullable=False),
        sa.Column('method', sa.String(10), nullable=False),
        sa.Column('status_code', sa.Integer, nullable=False),
        sa.Column('latency_ms', sa.Integer, nullable=True),
        sa.Column('tokens_used', sa.Integer, nullable=True),
        sa.Column('model_used', sa.String(100), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('request_metadata', postgresql.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_api_usage_logs_user_id', 'api_usage_logs', ['user_id'])
    op.create_index('ix_api_usage_logs_created_at', 'api_usage_logs', ['created_at'])
    op.create_index('ix_api_usage_logs_endpoint', 'api_usage_logs', ['endpoint'])


def downgrade() -> None:
    op.drop_table('api_usage_logs')
    op.drop_table('notes')
    op.drop_table('bookmarks')
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('document_chunks')
    op.drop_table('documents')
    op.drop_table('collections')
    op.drop_table('users')
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS documenttype")
    op.execute("DROP TYPE IF EXISTS documentstatus")
    op.execute("DROP TYPE IF EXISTS messagerole")
