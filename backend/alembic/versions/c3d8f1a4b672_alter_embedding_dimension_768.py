"""alter embedding dimension to 768 (local Ollama nomic-embed-text, not OpenAI)

Revision ID: c3d8f1a4b672
Revises: 5a960e39e039
Create Date: 2026-08-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy

# revision identifiers, used by Alembic.
revision: str = 'c3d8f1a4b672'
down_revision: Union[str, Sequence[str], None] = '5a960e39e039'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # document_chunks is still empty at this point (Phase 4 ingestion hasn't run yet),
    # so drop-and-recreate is safe — no cast/data-loss concern.
    op.drop_index('ix_document_chunks_embedding_hnsw', table_name='document_chunks')
    op.drop_column('document_chunks', 'embedding')
    op.add_column(
        'document_chunks',
        sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=False),
    )
    op.create_index(
        'ix_document_chunks_embedding_hnsw',
        'document_chunks',
        ['embedding'],
        unique=False,
        postgresql_using='hnsw',
        postgresql_ops={'embedding': 'vector_cosine_ops'},
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_document_chunks_embedding_hnsw', table_name='document_chunks')
    op.drop_column('document_chunks', 'embedding')
    op.add_column(
        'document_chunks',
        sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1536), nullable=False),
    )
    op.create_index(
        'ix_document_chunks_embedding_hnsw',
        'document_chunks',
        ['embedding'],
        unique=False,
        postgresql_using='hnsw',
        postgresql_ops={'embedding': 'vector_cosine_ops'},
    )
