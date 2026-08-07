from pydantic import BaseModel


class WatchlistCreate(BaseModel):
    company_name: str


class WatchlistResponse(WatchlistCreate):
    id: int

    class Config:
        from_attributes = True