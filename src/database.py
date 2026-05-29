import os
from datetime import datetime, UTC
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncAttrs
from sqlalchemy.orm import sessionmaker, DeclarativeBase, relationship
from dotenv import load_dotenv

# Search for .env in current or parent directory
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Load DATABASE_URL from env, fallback to SQLite for local tests if needed
# (though we'll use Postgres mostly now)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://vision:vision_pass@db:5432/vision_pipeline")


class Base(AsyncAttrs, DeclarativeBase):
    pass


def utc_now_naive() -> datetime:
    """Return UTC time without tzinfo for TIMESTAMP WITHOUT TIME ZONE columns."""
    return datetime.now(UTC).replace(tzinfo=None)


class Batch(Base):
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, default=lambda: f"Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now_naive)
    status = Column(String, default="processing")  # processing, completed

    items = relationship(
        "Item",
        back_populates="batch",
        cascade="all, delete-orphan")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"))
    image_path = Column(String)  # Path to local masked image
    # Path to original full image
    raw_image_path = Column(String, nullable=True)

    # State
    # processing, pending, approved, discarded, uploaded
    status = Column(String, default="processing")
    error = Column(Text, nullable=True)

    # Data
    product_type = Column(String, default="unknown")  # food, product
    ai_output = Column(JSONB, nullable=True)
    user_overrides = Column(JSONB, nullable=True)
    # Store the points for re-editing
    lasso_polygon = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=utc_now_naive)
    updated_at = Column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive)

    batch = relationship("Batch", back_populates="items")
    mappings = relationship(
        "ServiceMapping",
        back_populates="item",
        cascade="all, delete-orphan")


class ServiceMapping(Base):
    """Tracks where an item lives in external systems."""
    __tablename__ = "service_mappings"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    service_name = Column(String)  # homebox, mealie, etc.
    external_id = Column(String)  # ID in the external system
    external_url = Column(String, nullable=True)  # Link to external UI
    last_sync_payload = Column(JSONB, nullable=True)
    synced_at = Column(DateTime, default=utc_now_naive)

    item = relationship("Item", back_populates="mappings")


class ConfigSecret(Base):
    __tablename__ = "config_secrets"

    key = Column(String, primary_key=True, index=True)
    encrypted_value = Column(String)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String, primary_key=True, index=True)
    value = Column(JSONB, nullable=False)
    updated_at = Column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
    )


class ModelCatalog(Base):
    __tablename__ = "model_catalog"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String, unique=True, index=True, nullable=False)
    provider = Column(String, nullable=False)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_system = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now_naive)
    updated_at = Column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
    )


class PipelineDefinition(Base):
    __tablename__ = "pipeline_definitions"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_id = Column(String, unique=True, index=True)
    name = Column(String)
    schema = Column(JSONB, nullable=False)
    is_system = Column(Boolean, default=False)
    is_editable = Column(Boolean, default=True)
    service_target = Column(String, nullable=True)
    created_at = Column(DateTime, default=utc_now_naive)
    updated_at = Column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
    )


engine = create_async_engine(DATABASE_URL, echo=False)
async_session_local = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False)  # type: ignore


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
