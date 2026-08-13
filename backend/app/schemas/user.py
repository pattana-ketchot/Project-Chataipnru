import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    created_at: datetime


class UserProfileUpsert(BaseModel):
    education_level: str | None = None
    field_of_study: str | None = None
    current_role: str | None = None
    career_goal: str | None = None
    skills: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    language_preference: str = "th"


class UserProfileOut(UserProfileUpsert):
    model_config = ConfigDict(from_attributes=True)
    updated_at: datetime


class RequirementCreate(BaseModel):
    req_type: str = Field(max_length=64)
    req_value: str = Field(max_length=512)
    priority: int = Field(default=3, ge=1, le=5)


class RequirementOut(RequirementCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
