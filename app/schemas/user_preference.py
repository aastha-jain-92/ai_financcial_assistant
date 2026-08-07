from pydantic import BaseModel


class UserPreferenceCreate(BaseModel):
    role: str
    market: str
    briefing_time: str


class UserPreferenceResponse(UserPreferenceCreate):
    id: int

    class Config:
        from_attributes = True