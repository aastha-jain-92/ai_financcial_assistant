from pydantic import BaseModel


class NotificationPreferenceCreate(BaseModel):
    notification_type: str


class NotificationPreferenceResponse(
    NotificationPreferenceCreate
):
    id: int

    class Config:
        from_attributes = True