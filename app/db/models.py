from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base

class LocalCampaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True)  # Keitaro Campaign ID
    name = Column(String, nullable=False)
    group_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    streams = relationship("LocalStream", back_populates="campaign", cascade="all, delete-orphan")


class LocalStream(Base):
    __tablename__ = "streams"

    id = Column(Integer, primary_key=True)  # Keitaro Stream ID
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    type = Column(String, default="regular")
    schema = Column(String, default="landings")  # 'redirect' или 'landings'
    is_dirty = Column(Boolean, default=False)     # True = желтый поток (есть локальные изменения)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    campaign = relationship("LocalCampaign", back_populates="streams")
    offers = relationship("LocalStreamOffer", back_populates="stream", cascade="all, delete-orphan")


class LocalStreamOffer(Base):
    __tablename__ = "stream_offers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stream_id = Column(Integer, ForeignKey("streams.id", ondelete="CASCADE"), nullable=False)
    offer_id = Column(Integer, nullable=False)     # Keitaro Offer ID
    offer_name = Column(String, nullable=True)     # Человекочитаемое имя для UI
    share = Column(Integer, default=0)             # Вес в процентах (0-100)
    is_pinned = Column(Boolean, default=False)     # Зафиксирован ли вес
    status = Column(String, default="active")      # 'active' или 'removed' (серенький в архиве)
    created_at = Column(DateTime, default=datetime.utcnow)

    stream = relationship("LocalStream", back_populates="offers")