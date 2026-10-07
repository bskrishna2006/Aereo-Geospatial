"""Initial schema for file_records and feature_records

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-07 12:00:00.000000

"""

from typing import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. file_records table
    op.create_table(
        "file_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=50), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="UPLOADED"),
        sa.Column("feature_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_crs", sa.String(length=100), nullable=True),
        sa.Column("measurement_crs", sa.String(length=100), nullable=True),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("summary_stats", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_file_records_id"), "file_records", ["id"], unique=False)
    op.create_index(op.f("ix_file_records_status"), "file_records", ["status"], unique=False)

    # 2. feature_records table
    op.create_table(
        "feature_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("feature_index", sa.Integer(), nullable=False),
        sa.Column("geometry_type", sa.String(length=50), nullable=False),
        sa.Column("properties", sa.JSON(), nullable=True),
        sa.Column("source_geometry", sa.JSON(), nullable=True),
        sa.Column("measurement_type", sa.String(length=50), nullable=True),
        sa.Column("measurement_value", sa.Float(), nullable=True),
        sa.Column("measurement_unit", sa.String(length=20), nullable=True),
        sa.Column("measurement_crs", sa.String(length=100), nullable=True),
        sa.Column("calculation_metadata", sa.JSON(), nullable=True),
        sa.Column("processing_status", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["file_id"], ["file_records.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_feature_records_id"), "feature_records", ["id"], unique=False)
    op.create_index(
        op.f("ix_feature_records_file_id"), "feature_records", ["file_id"], unique=False
    )
    op.create_index(
        op.f("ix_feature_records_feature_index"), "feature_records", ["feature_index"], unique=False
    )
    op.create_index(
        op.f("ix_feature_records_processing_status"),
        "feature_records",
        ["processing_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_feature_records_processing_status"), table_name="feature_records")
    op.drop_index(op.f("ix_feature_records_feature_index"), table_name="feature_records")
    op.drop_index(op.f("ix_feature_records_file_id"), table_name="feature_records")
    op.drop_index(op.f("ix_feature_records_id"), table_name="feature_records")
    op.drop_table("feature_records")

    op.drop_index(op.f("ix_file_records_status"), table_name="file_records")
    op.drop_index(op.f("ix_file_records_id"), table_name="file_records")
    op.drop_table("file_records")
