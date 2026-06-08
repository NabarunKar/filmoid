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
