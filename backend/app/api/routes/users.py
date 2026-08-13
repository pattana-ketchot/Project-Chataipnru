from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User, UserProfile, UserRequirement
from app.schemas.user import (
    RequirementCreate,
    RequirementOut,
    UserOut,
    UserProfileOut,
    UserProfileUpsert,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def get_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.put("/me/profile", response_model=UserProfileOut)
def upsert_my_profile(
    payload: UserProfileUpsert,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfile:
    profile = db.get(UserProfile, user.id)
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
    for field, value in payload.model_dump().items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/me/profile", response_model=UserProfileOut)
def get_my_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserProfile:
    profile = db.get(UserProfile, user.id)
    if profile is None:
        profile = UserProfile(user_id=user.id)
    return profile


@router.post("/me/requirements", response_model=RequirementOut, status_code=201)
def add_requirement(
    payload: RequirementCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserRequirement:
    req = UserRequirement(user_id=user.id, **payload.model_dump())
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.get("/me/requirements", response_model=list[RequirementOut])
def list_requirements(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[UserRequirement]:
    return db.query(UserRequirement).filter(UserRequirement.user_id == user.id).all()
