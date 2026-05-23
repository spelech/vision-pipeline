import os
import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, ForeignKey, Text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

DATABASE_URL = "sqlite+aiosqlite:///./data/vision_pipeline.db"

# Ensure data directory exists
os.makedirs("./data", exist_ok=True)
os.makedirs("./data/uploads", exist_ok=True)

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
    image_path = Column(String) # Path to local stored file
    
    # State
    status = Column(String, default="processing") # processing, pending, approved, discarded, uploaded
    error = Column(Text, nullable=True)
    
    # Data
    product_type = Column(String, default="unknown") # food, product
    ai_output = Column(JSON, nullable=True)
    user_overrides = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    batch = relationship("Batch", back_populates="items")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
