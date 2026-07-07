import uuid
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from .custom_types import CIText
from sqlalchemy.sql import func
from .database import Base
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(CIText, unique=True, index=True, nullable=False)
    email = Column(CIText, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RecommendationSession(Base):
    __tablename__ = "recommendation_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    recommendations = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", backref="recommendation_sessions")


class UserRating(Base):
    __tablename__ = "user_ratings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tmdb_id = Column(Integer, nullable=False)

    # Lightweight metadata snapshot for rendering without TMDB lookups.
    movie_title = Column(String, nullable=False)
    poster_path = Column(String, nullable=True)
    release_date = Column(String, nullable=True)

    rating = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", backref="ratings")


class MissingTitle(Base):
    __tablename__ = "missing_titles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    tmdb_id = Column(Integer, nullable=False, unique=True, index=True)
    movie_title = Column(String, nullable=False)
    release_year = Column(Integer, nullable=True)
    letterboxd_slug = Column(String, nullable=True)

    reason = Column(String, nullable=False, default="missing_model_mapping")
    source = Column(String, nullable=False, default="svd_input_mapping")
    occurrence_count = Column(Integer, nullable=False, default=1)
    resolved = Column(Boolean, nullable=False, default=False)
