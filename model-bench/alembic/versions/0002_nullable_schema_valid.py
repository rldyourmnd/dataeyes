"""nullable_schema_valid

Revision ID: 0002_nullable_schema_valid
Revises: 0001_initial
Create Date: 2026-06-10
"""
from alembic import op

revision = '0002_nullable_schema_valid'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('model_results', 'schema_valid', nullable=True, server_default=None)


def downgrade() -> None:
    op.execute("UPDATE model_results SET schema_valid = FALSE WHERE schema_valid IS NULL")
    op.alter_column('model_results', 'schema_valid', nullable=False, server_default='false')
