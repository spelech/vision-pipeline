import os
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, ForeignKey, Text, Table
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
import uuid

# Load DATABASE_URL from env, fallback to SQLite for local tests if needed (though we'll use Postgres mostly now)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://vision:vision_pass@db:5432/vision_pipeline")

Base = declarative_base()

class Batch(Base):
    __tablename__ = "batches"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, default=lambda: f"Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="processing") # processing, completed
    
    items = relationship("Item", back_populates="batch", cascade="all, delete-orphan")

class Item(Base):
    __tablename__ = "items"
    
    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"))
    image_path = Column(String) # Path to local masked image
    raw_image_path = Column(String, nullable=True) # Path to original full image
    
    # State
    status = Column(String, default="processing") # processing, pending, approved, discarded, uploaded
    error = Column(Text, nullable=True)
    
    # Data
    product_type = Column(String, default="unknown") # food, product
    ai_output = Column(JSONB, nullable=True)
    user_overrides = Column(JSONB, nullable=True)
    lasso_polygon = Column(JSONB, nullable=True) # Store the points for re-editing
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    batch = relationship("Batch", back_populates="items")
    mappings = relationship("ServiceMapping", back_populates="item", cascade="all, delete-orphan")

class ServiceMapping(Base):
    """Tracks where an item lives in external systems."""
    __tablename__ = "service_mappings"
    
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    service_name = Column(String) # homebox, mealie, etc.
    external_id = Column(String) # ID in the external system
    external_url = Column(String, nullable=True) # Link to external UI
    last_sync_payload = Column(JSONB, nullable=True)
    synced_at = Column(DateTime, default=datetime.utcnow)

    item = relationship("Item", back_populates="mappings")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
