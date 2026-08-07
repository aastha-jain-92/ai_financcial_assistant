from pydantic import BaseModel


class UserCreate(BaseModel):
    telegram_id: int
    full_name: str


class UserResponse(UserCreate):
    id: int
    onboarding_completed: bool

    class Config:
        from_attributes = True