from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..auth import get_current_active_user, get_db

router = APIRouter()

@router.get("/me", response_model=schemas.UserOut)
def read_users_me(current_user: models.User = Depends(get_current_active_user)):
    return current_user


@router.get("/me/recommendations", response_model=schemas.RecommendationSessionSummaryList)
def list_my_recommendations(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    sessions = crud.list_recommendation_sessions_for_user(db, user_id=current_user.id)

    summaries: list[schemas.RecommendationSessionSummary] = []
    for s in sessions:
        recs = s.recommendations or []
        preview_titles: list[str] = []
        for r in recs[:3]:
            if isinstance(r, dict):
                title = r.get("title")
                if isinstance(title, str) and title.strip():
                    preview_titles.append(title.strip())

        created_at = s.created_at.isoformat() if getattr(s, "created_at", None) else ""
        summaries.append(
            schemas.RecommendationSessionSummary(
                session_id=s.id,
                created_at=created_at,
                recommendation_count=len(recs),
                preview_titles=preview_titles,
            )
        )

    return schemas.RecommendationSessionSummaryList(sessions=summaries)


@router.post("/me/ratings", response_model=schemas.UserRatingOut)
def upsert_my_rating(
    rating_in: schemas.UserRatingIn,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    saved = crud.upsert_user_rating(db, user_id=current_user.id, rating_in=rating_in)
    return schemas.UserRatingOut(
        id=saved.id,
        user_id=saved.user_id,
        tmdb_id=saved.tmdb_id,
        movie_title=saved.movie_title,
        poster_path=saved.poster_path,
        release_date=saved.release_date,
        rating=saved.rating,
        created_at=saved.created_at.isoformat() if saved.created_at else "",
        updated_at=saved.updated_at.isoformat() if saved.updated_at else "",
    )


@router.get("/me/ratings", response_model=schemas.UserRatingList)
def list_my_ratings(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    rows = crud.list_user_ratings_for_user(db, user_id=current_user.id, limit=20)
    ratings = [
        schemas.UserRatingOut(
            id=r.id,
            user_id=r.user_id,
            tmdb_id=r.tmdb_id,
            movie_title=r.movie_title,
            poster_path=r.poster_path,
            release_date=r.release_date,
            rating=r.rating,
            created_at=r.created_at.isoformat() if r.created_at else "",
            updated_at=r.updated_at.isoformat() if r.updated_at else "",
        )
        for r in rows
    ]
    return schemas.UserRatingList(ratings=ratings)


@router.delete("/me/ratings/{tmdb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_rating(
    tmdb_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    deleted = crud.delete_user_rating(db, user_id=current_user.id, tmdb_id=tmdb_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rating not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
