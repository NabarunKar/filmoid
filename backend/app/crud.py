from sqlalchemy.orm import Session
import uuid
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

def create_recommendation_session(db: Session, session_id: uuid.UUID, recommendations: list[schemas.MovieOut]):
    recommendations_data = [rec.model_dump() for rec in recommendations]
    db_session = models.RecommendationSession(
        id=session_id,
        recommendations=recommendations_data
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session
