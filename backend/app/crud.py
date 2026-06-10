from sqlalchemy.orm import Session
import uuid
from sqlalchemy import desc
from . import models, schemas
from .auth import get_password_hash

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = models.User(username=user.username, email=user.email, password_hash=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_recommendation_session(db: Session, session_id: uuid.UUID):
    return db.query(models.RecommendationSession).filter(models.RecommendationSession.id == session_id).first()

def create_recommendation_session(
    db: Session,
    session_id: uuid.UUID,
    recommendations: list[schemas.MovieOut],
    user_id: uuid.UUID | None = None,
):
    recommendations_data = [rec.model_dump() for rec in recommendations]
    db_session = models.RecommendationSession(
        id=session_id,
        recommendations=recommendations_data,
        user_id=user_id,
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session


def list_recommendation_sessions_for_user(db: Session, user_id: uuid.UUID, limit: int = 50):
    return (
        db.query(models.RecommendationSession)
        .filter(models.RecommendationSession.user_id == user_id)
        .order_by(desc(models.RecommendationSession.created_at))
        .limit(limit)
        .all()
    )


def upsert_user_rating(db: Session, user_id: uuid.UUID, rating_in: schemas.UserRatingIn) -> models.UserRating:
    existing = (
        db.query(models.UserRating)
        .filter(models.UserRating.user_id == user_id, models.UserRating.tmdb_id == int(rating_in.tmdb_id))
        .first()
    )

    if existing:
        existing.rating = float(rating_in.rating)
        existing.movie_title = rating_in.movie_title
        existing.poster_path = rating_in.poster_path
        existing.release_date = rating_in.release_date
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    db_rating = models.UserRating(
        user_id=user_id,
        tmdb_id=int(rating_in.tmdb_id),
        rating=float(rating_in.rating),
        movie_title=rating_in.movie_title,
        poster_path=rating_in.poster_path,
        release_date=rating_in.release_date,
    )
    db.add(db_rating)
    db.commit()
    db.refresh(db_rating)
    return db_rating


def list_user_ratings_for_user(db: Session, user_id: uuid.UUID, limit: int = 20):
    return (
        db.query(models.UserRating)
        .filter(models.UserRating.user_id == user_id)
        .order_by(desc(models.UserRating.updated_at))
        .limit(limit)
        .all()
    )


def delete_user_rating(db: Session, user_id: uuid.UUID, tmdb_id: int) -> bool:
    row = (
        db.query(models.UserRating)
        .filter(models.UserRating.user_id == user_id, models.UserRating.tmdb_id == int(tmdb_id))
        .first()
    )
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True
