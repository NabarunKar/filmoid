from __future__ import annotations
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import uuid

class RatingIn(BaseModel):
    tmdbId: int = Field(..., ge=1)
    rating: float = Field(..., ge=1, le=10)


class RecommendRequest(BaseModel):
    tmdbApiKey: str = Field(..., min_length=5)
    ratings: List[RatingIn] = Field(default_factory=list)
    topN: int = Field(10, ge=1, le=50)


class MovieOut(BaseModel):
    id: int
    title: str
    poster_path: Optional[str] = None
    score: float
    release_date: Optional[str] = None


class RecommendResponse(BaseModel):
    sessionId: str
    recommendations: List[MovieOut]

    class Config:
        from_attributes = True

class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserOut(UserBase):
    id: uuid.UUID

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None


class RecommendationSessionSummary(BaseModel):
    session_id: uuid.UUID
    created_at: str
    recommendation_count: int
    preview_titles: List[str] = Field(default_factory=list, max_length=3)


class RecommendationSessionSummaryList(BaseModel):
    sessions: List[RecommendationSessionSummary]


class UserRatingIn(BaseModel):
    tmdb_id: int = Field(..., ge=1)
    movie_title: str = Field(..., min_length=1)
    poster_path: Optional[str] = None
    release_date: Optional[str] = None
    rating: float = Field(..., ge=1, le=10)


class UserRatingOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    tmdb_id: int
    movie_title: str
    poster_path: Optional[str] = None
    release_date: Optional[str] = None
    rating: float
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class UserRatingList(BaseModel):
    ratings: List[UserRatingOut]
