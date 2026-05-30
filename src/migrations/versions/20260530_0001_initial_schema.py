"""initial schema

Revision ID: 20260530_0001
Revises: 
Create Date: 2026-05-30 00:00:00.000000
"""

from __future__ import annotations

# pylint: disable=invalid-name,line-too-long

from alembic import op  # type: ignore[import-untyped]
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260530_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_index(op.f("ix_app_settings_key"), "app_settings", ["key"], unique=False)

    op.create_table(
        "batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_batches_id"), "batches", ["id"], unique=False)

    op.create_table(
        "config_secrets",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("encrypted_value", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_index(op.f("ix_config_secrets_key"), "config_secrets", ["key"], unique=False)

    op.create_table(
        "model_catalog",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_model_catalog_id"), "model_catalog", ["id"], unique=False)
    op.create_index(op.f("ix_model_catalog_model_id"), "model_catalog", ["model_id"], unique=True)

    op.create_table(
        "pipeline_definitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pipeline_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=True),
        sa.Column("is_editable", sa.Boolean(), nullable=True),
        sa.Column("service_target", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pipeline_definitions_id"), "pipeline_definitions", ["id"], unique=False)
    op.create_index(op.f("ix_pipeline_definitions_pipeline_id"), "pipeline_definitions", ["pipeline_id"], unique=True)

    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=True),
        sa.Column("image_path", sa.String(), nullable=True),
        sa.Column("raw_image_path", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("product_type", sa.String(), nullable=True),
        sa.Column("ai_output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("user_overrides", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("lasso_polygon", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_items_id"), "items", ["id"], unique=False)

    op.create_table(
        "service_mappings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("service_name", sa.String(), nullable=True),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("external_url", sa.String(), nullable=True),
        sa.Column("last_sync_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_service_mappings_id"), "service_mappings", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_service_mappings_id"), table_name="service_mappings")
    op.drop_table("service_mappings")

    op.drop_index(op.f("ix_items_id"), table_name="items")
    op.drop_table("items")

    op.drop_index(op.f("ix_pipeline_definitions_pipeline_id"), table_name="pipeline_definitions")
    op.drop_index(op.f("ix_pipeline_definitions_id"), table_name="pipeline_definitions")
    op.drop_table("pipeline_definitions")

    op.drop_index(op.f("ix_model_catalog_model_id"), table_name="model_catalog")
    op.drop_index(op.f("ix_model_catalog_id"), table_name="model_catalog")
    op.drop_table("model_catalog")

    op.drop_index(op.f("ix_config_secrets_key"), table_name="config_secrets")
    op.drop_table("config_secrets")

    op.drop_index(op.f("ix_batches_id"), table_name="batches")
    op.drop_table("batches")

    op.drop_index(op.f("ix_app_settings_key"), table_name="app_settings")
    op.drop_table("app_settings")
